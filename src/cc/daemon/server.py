"""
CC Daemon — Unix socket server.

Listens at ~/.cc-cli/cc.sock, accepts JSON-RPC 2.0 requests,
dispatches via the RPC router, returns JSON-RPC 2.0 responses.

Protocol: newline-delimited JSON over a Unix domain socket.
  Request:  {"jsonrpc": "2.0", "method": "env.get_active_database", "params": {}, "id": 1}
  Response: {"jsonrpc": "2.0", "result": "my_db", "id": 1}
  Error:    {"jsonrpc": "2.0", "error": {"code": -32601, "message": "..."}, "id": 1}

One thread per connection — SQLite WAL handles concurrent reads, writes queue.
"""
import json
import logging
import os
import queue
import signal
import socket
import sys
import threading
import time

from cc.utils.dotenv import load as _load_dotenv
_load_dotenv()

from cc.daemon.router import RPCError, dispatch
from cc.utils.constants import Constants
from cc.utils.errors import CCError
from cc.utils.logger import setup_logging, setup_rpc_logging

# Daemon always logs at DEBUG level — console output is lost when backgrounded,
# but everything lands in ~/.cc-cli/logs/cc.log
setup_logging(debug_mode=True)
setup_rpc_logging()
log = logging.getLogger("CC")
rpc_log = logging.getLogger("RPC")

# ── Runtime stats (read by system.health) ────────────────────────────────────
_started_at: float = time.time()
_rpc_count: int = 0
_rpc_count_lock = threading.Lock()
_last_error: str | None = None


_REDACT_KEYS = {"password", "token", "pat", "cookie", "session", "secret", "key"}
# Settings whose VALUE is a credential. `setting.upsert(key=..., value=...)`
# passes the secret under the param literally named "value", which no
# param-name match can catch — redact by the setting key instead.
_REDACT_SETTING_KEYS = {"pg.connection", "sh_session_id"}


def _redact_setting_params(params: dict) -> dict:
    """For setting.* methods: mask `value` when the target setting key is
    credential-shaped (matches _REDACT_KEYS) or explicitly sensitive."""
    key = str(params.get("key") or params.get("name") or "").lower()
    if "value" in params and key and (
        key in _REDACT_SETTING_KEYS or any(k in key for k in _REDACT_KEYS)
    ):
        return {**params, "value": "[REDACTED]"}
    return params


def _summarize(value, max_str=80, _key=None):
    """Summarize a value for logging — no full data dumps, no sensitive values."""
    if _key and any(k in _key.lower() for k in _REDACT_KEYS):
        return "[REDACTED]"
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if len(value) <= max_str:
            return repr(value)
        return repr(value[:max_str]) + f"…[{len(value)} chars]"
    if isinstance(value, list):
        return f"list[{len(value)}]"
    if isinstance(value, dict):
        keys = list(value.keys())
        if len(keys) <= 4:
            return "{" + ", ".join(f"{k}: {_summarize(value[k], _key=k)}" for k in keys) + "}"
        return f"dict[{len(keys)} keys]"
    return type(value).__name__


def _handle_subscribe(conn: socket.socket, req_id):
    """Long-lived subscribe connection — push events until client disconnects."""
    from cc.daemon.event_bus import subscribe as _bus_subscribe

    q, unsubscribe = _bus_subscribe()
    _send(conn, {"jsonrpc": "2.0", "result": "subscribed", "id": req_id})
    log.debug("Subscribe connection established")
    try:
        while True:
            try:
                event = q.get(timeout=30)
                conn.sendall((json.dumps({"event": event}) + "\n").encode())
            except queue.Empty:
                # Send a keep-alive comment — client ignores unknown frames
                conn.sendall(b'{"ping":1}\n')
    except (OSError, BrokenPipeError, ConnectionResetError):
        pass  # Client disconnected
    finally:
        unsubscribe()
        conn.close()
        log.debug("Subscribe connection closed")


def _handle_connection(conn: socket.socket):
    """Read one request, dispatch, write response, close."""
    keep_alive = False
    try:
        data = b""
        while not data.endswith(b"\n"):
            chunk = conn.recv(4096)
            if not chunk:
                return
            data += chunk

        try:
            request = json.loads(data.decode())
        except json.JSONDecodeError:
            _send(conn, _error(None, -32700, "Parse error"))
            return

        req_id = request.get("id")
        method = request.get("method")
        params = request.get("params") or {}

        if not method:
            _send(conn, _error(req_id, -32600, "Missing method"))
            return

        # Subscribe — long-lived connection, ownership transferred to _handle_subscribe
        if method == "system.subscribe":
            keep_alive = True
            _handle_subscribe(conn, req_id)
            return

        try:
            log_params = params
            if method.startswith("setting.") and isinstance(params, dict):
                log_params = _redact_setting_params(params)
            param_summary = _summarize(log_params)
            log.debug(f"RPC → {method}({param_summary})")
            t0 = time.perf_counter()
            result = dispatch(method, params)
            elapsed = (time.perf_counter() - t0) * 1000
            result_summary = _summarize(result)
            log.debug(f"RPC ← {method} = {result_summary} ({elapsed:.1f}ms)")
            rpc_log.info(f"OK  {method}({param_summary}) → {result_summary}  {elapsed:.1f}ms")
            with _rpc_count_lock:
                global _rpc_count
                _rpc_count += 1
            _send(conn, {"jsonrpc": "2.0", "result": result, "id": req_id})
        except RPCError as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.warning(f"RPC error {method}: [{e.code}] {e.message}")
            rpc_log.warning(f"ERR {method}({param_summary}) → [{e.code}] {e.message}  {elapsed:.1f}ms")
            _send(conn, _error(req_id, e.code, e.message))
        except CCError as e:
            elapsed = (time.perf_counter() - t0) * 1000
            log.debug(f"RPC CCError in {method}: {e}")
            rpc_log.warning(f"ERR {method}({param_summary}) → CCError: {e}  {elapsed:.1f}ms")
            _send(conn, _error(req_id, -32001, str(e)))
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            global _last_error
            _last_error = f"{method}: {e}"
            log.exception(f"RPC unhandled error in {method}")
            rpc_log.error(f"ERR {method}({param_summary}) → unhandled: {e}  {elapsed:.1f}ms")
            _send(conn, _error(req_id, -32603, str(e)))

    finally:
        if not keep_alive:
            conn.close()


def _send(conn: socket.socket, payload: dict):
    conn.sendall((json.dumps(payload) + "\n").encode())


def _error(req_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "error": {"code": code, "message": message}, "id": req_id}


def _write_pid():
    with open(Constants.DAEMON_PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _cleanup():
    for path in (Constants.SOCKET_PATH, Constants.DAEMON_PID_FILE):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def run():
    """Start the daemon. Blocks until SIGTERM/SIGINT."""

    # Remove stale socket from a previous crash
    try:
        os.unlink(Constants.SOCKET_PATH)
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(Constants.SOCKET_PATH)
    os.chmod(Constants.SOCKET_PATH, 0o600)
    server.listen(32)

    _write_pid()
    log.debug(f"CC daemon started — PID {os.getpid()}, socket {Constants.SOCKET_PATH}")

    # Warm ORM registry — import all models once so Property descriptors bind at startup,
    # not on the first request. Subsequent imports in service functions are sys.modules hits.
    from cc.base.arm import (  # noqa: F401
        AppState, Backup, Database, Device, DevicePath, Environment, KnowledgeIndex,
        Module, Project, Repository, Setting, SkillTag, SwitchLog, Version, Workspace,
    )
    log.debug("ORM registry warmed.")

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.DAEMON_READY)

    try:
        from cc.sync.auto import start as _start_auto_sync
        _start_auto_sync()
    except ImportError:
        pass

    # Background PG metadata cache — keeps the Database table mirroring live
    # Postgres so readers never block on psql.
    try:
        from cc.daemon.db_sync import start as _start_db_cache
        _start_db_cache()
    except Exception as e:
        log.debug(f"db-cache sync not started: {e}")

    def _shutdown(signum, frame):
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while True:
            conn, _ = server.accept()
            threading.Thread(target=_handle_connection, args=(conn,), daemon=True).start()
    finally:
        _cleanup()
