"""
CC Sync HTTP Client — talks to a remote CC Sync server over HTTP.

Reads server URL and API key from environment variables or cc settings:
  CC_SERVER=https://cc.example.com   (or setting: sync.server_url)
  CC_API_KEY=<uuid>                  (or setting: sync.api_key)
"""
import json
import logging
import os
import urllib.request
import urllib.error

log = logging.getLogger("CC")

_REQUEST_ID = 0


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


def _get_config() -> tuple[str | None, str | None]:
    """Return (server_url, api_key) from env vars, falling back to cc settings."""
    server = os.environ.get("CC_SERVER")
    api_key = os.environ.get("CC_API_KEY")

    if server and api_key:
        return server.rstrip("/"), api_key

    try:
        from cc.base.arm.setting import Setting
        from cc.base.db import database_connection_manager

        with database_connection_manager():
            if not server:
                s = Setting.find_by(name="sync.server_url", limit=1)
                if s:
                    server = s.value.rstrip("/")
            if not api_key:
                s = Setting.find_by(name="sync.api_key", limit=1)
                if s:
                    api_key = s.value
    except Exception:
        pass

    return server, api_key


def is_configured() -> bool:
    """Check if sync server connection is configured."""
    server, api_key = _get_config()
    return bool(server and api_key)


def call(method: str, **params) -> dict:
    """Make a JSON-RPC call to the remote sync server.

    Returns the result dict, or raises on error.
    """
    server, api_key = _get_config()
    if not server or not api_key:
        raise RuntimeError(
            "Sync server not configured. Set CC_SERVER and CC_API_KEY "
            "environment variables, or use 'cc config' to set sync.server_url "
            "and sync.api_key."
        )

    url = f"{server}/rpc"
    from cc.sync.crypto import encrypt

    request_body = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": _next_id(),
    }

    request_body = encrypt(request_body, api_key)
    data = json.dumps(request_body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "cc-sync-client/1.0",
        },
        method="POST",
    )

    from cc.sync.crypto import is_encrypted, decrypt

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            response = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        if e.code in (401, 403):
            key_hint = f"{api_key[:8]}…" if api_key else "(none)"
            raise RuntimeError(
                f"Sync server rejected this device's API key ({key_hint}).\n"
                f"  That key is not registered on {server}.\n"
                f"  Fix: run `cc sync setup` to configure a valid key, or copy "
                f"CC_API_KEY from a working device's ~/.cc-cli/.env.\n"
                f"  Note: `cc sync register` run locally only creates a key in the "
                f"LOCAL database — it does not enroll this machine on the remote server."
            ) from e
        raise RuntimeError(f"Sync server returned HTTP {e.code}: {body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Cannot reach sync server at {server}: {e.reason}") from e

    if is_encrypted(response):
        response = decrypt(response, api_key)

    if "error" in response:
        err = response["error"]
        raise RuntimeError(f"Sync server error [{err.get('code')}]: {err.get('message')}")

    return response.get("result")


def health() -> dict | None:
    """Check sync server health. Returns status dict or None if unreachable."""
    server, _ = _get_config()
    if not server:
        return None

    url = f"{server}/health"
    req = urllib.request.Request(url, method="GET", headers={"User-Agent": "cc-sync-client/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def verify(server: str, api_key: str) -> tuple[bool, str]:
    """Probe a candidate (server, api_key) pair without touching stored config.

    Used by `cc sync setup` to validate credentials before writing them to
    ``~/.cc-cli/.env``. Returns ``(ok, message)``.
    """
    server = (server or "").rstrip("/")
    if not server or not api_key:
        return False, "Server URL and API key are both required."

    # Reachability first — unauthenticated GET /health.
    health_url = f"{server}/health"
    hreq = urllib.request.Request(health_url, method="GET", headers={"User-Agent": "cc-sync-client/1.0"})
    try:
        with urllib.request.urlopen(hreq, timeout=10) as resp:
            json.loads(resp.read().decode())
    except urllib.error.URLError as e:
        return False, f"Cannot reach {server}: {getattr(e, 'reason', e)}"
    except Exception as e:
        return False, f"Cannot reach {server}: {e}"

    # Authenticated probe — temporarily expose the candidate creds to call()
    # and run a cheap pull (far-future `since` returns no rows but exercises auth).
    prev_server = os.environ.get("CC_SERVER")
    prev_key = os.environ.get("CC_API_KEY")
    os.environ["CC_SERVER"] = server
    os.environ["CC_API_KEY"] = api_key
    try:
        call("sync.pull", since="2999-01-01T00:00:00")
        return True, "Server reachable and API key accepted."
    except RuntimeError as e:
        msg = str(e)
        if "rejected this device's API key" in msg:
            return False, "Server reachable, but the API key was rejected — it is not registered on the server."
        return False, msg
    finally:
        for var, prev in (("CC_SERVER", prev_server), ("CC_API_KEY", prev_key)):
            if prev is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = prev
