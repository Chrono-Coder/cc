"""
CC Sync HTTP Server — standalone process exposing sync.* RPC over HTTP.

Runs on the central server (e.g. Raspberry Pi). Only sync.* namespace
methods are allowed — the full daemon RPC surface is not exposed.

Usage:
    python -m cc.sync.http_server --port 9100
    # or via CLI: cc sync server start
"""
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cc.daemon.router import RPCError, dispatch
from cc.utils.constants import Constants
from cc.utils.logger import setup_logging

log = logging.getLogger("CC")

# Explicit method allowlist, not a namespace: the other sync.* methods
# (register_device, link_project, mark_synced, stamp_sync_ids) are local
# enrollment/bookkeeping and must never be reachable over the network.
# register_device in particular returns API keys.
ALLOWED_METHODS = {"sync.push", "sync.pull"}
DEFAULT_PORT = 9100
MAX_BODY_BYTES = 64 * 1024 * 1024  # sync payloads are row dumps; 64 MB is generous


def _validate_api_key(api_key: str) -> dict | None:
    """Validate an API key against the device table. Returns device dict or None."""
    from cc.base.arm.device import Device
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        device = Device.find_by(api_key=api_key, limit=1)
        if device:
            from datetime import datetime, timezone
            device.update({"last_seen_at": datetime.now(timezone.utc).isoformat()})
            return {"id": device.id, "name": device.name}
    return None


def _json_rpc_error(req_id, code, message):
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}


def _json_rpc_result(req_id, result):
    return {"jsonrpc": "2.0", "result": result, "id": req_id}


class SyncServer(ThreadingHTTPServer):
    # Threaded so one slow client can't stall every other device's sync;
    # daemon_threads so a wedged handler can't block shutdown.
    allow_reuse_address = True
    daemon_threads = True


class SyncHandler(BaseHTTPRequestHandler):
    server_version = "CCSyncServer/0.1"
    timeout = 30  # per-request socket timeout (slowloris guard)

    def log_message(self, format, *args):
        log.debug(f"HTTP {args[0]}")

    def do_POST(self):
        if self.path != "/rpc":
            self._respond(404, {"error": "Not found"})
            return

        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._respond(401, _json_rpc_error(None, -32000, "Missing Authorization header"))
            return

        api_key = auth_header[7:]
        device = _validate_api_key(api_key)
        if not device:
            self._respond(403, _json_rpc_error(None, -32000, "Invalid API key"))
            return

        try:
            content_length = int(self.headers.get("Content-Length", 0))
        except ValueError:
            self._respond(400, _json_rpc_error(None, -32600, "Bad Content-Length"))
            return
        if content_length > MAX_BODY_BYTES:
            self._respond(413, _json_rpc_error(None, -32600, "Payload too large"))
            return
        body = self.rfile.read(content_length)

        from cc.sync.crypto import is_encrypted, decrypt, encrypt

        try:
            request = json.loads(body)
        except json.JSONDecodeError:
            self._respond(400, _json_rpc_error(None, -32700, "Parse error"))
            return

        encrypted = is_encrypted(request)
        if encrypted:
            try:
                request = decrypt(request, api_key)
            except Exception:
                self._respond(400, _json_rpc_error(None, -32700, "Decryption failed"))
                return

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if not method:
            self._respond(400, _json_rpc_error(req_id, -32600, "Missing method"))
            return

        if method not in ALLOWED_METHODS:
            self._respond(403, _json_rpc_error(req_id, -32600, f"Method '{method}' not allowed on sync server"))
            return

        try:
            log.debug(f"HTTP RPC → {method} (device={device['name']})")
            result = dispatch(method, params)
            response = _json_rpc_result(req_id, result)
        except RPCError as e:
            response = _json_rpc_error(req_id, e.code, e.message)
        except Exception:
            # Full detail stays in the server log; remote clients get a
            # generic error (str(e) leaked paths and SQL text).
            log.exception(f"HTTP RPC error in {method}")
            response = _json_rpc_error(req_id, -32603, "Internal error")

        if encrypted:
            response = encrypt(response, api_key)
        self._respond(200, response)

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok", "server": "cc-sync"})
            return
        self._respond(404, {"error": "Not found"})

    def _respond(self, status, body):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        payload = json.dumps(body).encode()
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)


def run(port: int = DEFAULT_PORT, host: str = "0.0.0.0"):
    """Start the sync HTTP server. Blocks until interrupted."""
    from cc.utils.dotenv import load as _load_dotenv
    _load_dotenv()
    setup_logging(debug_mode=True)

    from cc.base.arm import (  # noqa: F401
        AppState, Backup, Database, Device, DevicePath, Environment,
        Module, Project, Setting,
        SwitchLog, Version, Workspace,
    )

    from cc.base.db import database_connection_manager, initialize_database
    with database_connection_manager():
        initialize_database()

    log.info(f"CC Sync server starting on {host}:{port}")
    log.warning(
        "The sync server speaks plain HTTP and trusts bearer keys on the wire. "
        "Run it only on a private, trusted network (LAN/VPN) or behind a "
        "TLS-terminating reverse proxy."
    )

    server = SyncServer((host, port), SyncHandler)

    def _shutdown(signum, frame):
        log.info("Sync server shutting down")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="CC Sync Server")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    run(port=args.port, host=args.host)
