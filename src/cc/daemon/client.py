"""
CC Daemon Client — connects to the daemon socket and makes RPC calls.

Auto-starts the daemon if the socket is missing, then retries once.
Used by the CLI and any other local caller that wants to talk to the daemon.
"""
import fcntl
import json
import os
import socket
import subprocess
import sys
import time

from cc.utils.constants import Constants
from cc.utils.errors import CCError, DaemonError

_REQUEST_ID = 0


def _next_id() -> int:
    global _REQUEST_ID
    _REQUEST_ID += 1
    return _REQUEST_ID


_SOCKET_TIMEOUT = 10  # seconds — prevents CLI hanging on a stuck daemon


def _connect() -> socket.socket:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(_SOCKET_TIMEOUT)
    sock.connect(Constants.SOCKET_PATH)
    return sock


def _socket_is_live() -> bool:
    """True if the daemon socket exists AND something is actually listening.

    A hard-killed daemon leaves the socket *file* behind; os.path.exists() then
    lies that the daemon is up. We must actually connect — the server unlinks
    and rebinds the stale path on startup, so this is the only reliable signal.
    """
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.5)
        s.connect(Constants.SOCKET_PATH)
        s.close()
        return True
    except OSError:
        return False


def _do_call(method: str, params: dict, timeout: int = _SOCKET_TIMEOUT):
    sock = _connect()
    sock.settimeout(timeout)
    try:
        request = {"jsonrpc": "2.0", "method": method, "params": params, "id": _next_id()}
        sock.sendall((json.dumps(request) + "\n").encode())

        data = b""
        while not data.endswith(b"\n"):
            chunk = sock.recv(4096)
            if not chunk:
                raise ConnectionError("Daemon closed connection before responding")
            data += chunk

        response = json.loads(data.decode())

        if "error" in response:
            err = response["error"]
            if err.get("code") == -32001:
                raise CCError(err["message"])
            raise DaemonError(err["message"])

        return response.get("result")
    finally:
        sock.close()


def _start_daemon():
    """Spawn the daemon as a detached background process."""
    # Use a lock file to prevent multiple callers racing to start the daemon
    lock_path = Constants.DAEMON_PID_FILE + ".lock"
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Another process is already starting it — wait up to 5s for it to bind
        lock_fd.close()
        for _ in range(50):
            time.sleep(0.1)
            if _socket_is_live():
                return
        return

    try:
        subprocess.Popen(
            [sys.executable, "-m", "cc.daemon"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Wait for the daemon to actually accept connections — not just for the
        # socket file to appear. (A stale file from a crash exists instantly but
        # refuses connections until the new daemon rebinds it.)
        # Exponential backoff: poll up to 5s total (0.1, 0.2, 0.4, 0.8, 1.6, 1.9s)
        delay = 0.1
        waited = 0.0
        while waited < 5.0:
            time.sleep(delay)
            waited += delay
            if _socket_is_live():
                return
            delay = min(delay * 2, 5.0 - waited)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


def subscribe():
    """
    Generator that yields event dicts from the daemon's pub/sub channel.

    Keeps the socket open until the daemon closes it or the caller breaks.
    Auto-starts the daemon if not running. Silently stops on disconnect.

    Usage:
        for event in subscribe():
            print(event["type"], event)
    """
    try:
        sock = _connect()
    except (FileNotFoundError, ConnectionRefusedError):
        _start_daemon()
        try:
            sock = _connect()
        except (FileNotFoundError, ConnectionRefusedError):
            return  # Daemon unavailable — yield nothing

    sock.settimeout(60)  # Longer timeout for long-lived connection
    request = {"jsonrpc": "2.0", "method": "system.subscribe", "params": {}, "id": _next_id()}
    sock.sendall((json.dumps(request) + "\n").encode())

    buf = ""
    try:
        while True:
            try:
                chunk = sock.recv(4096)
            except TimeoutError:
                continue  # Keep-alive timeout — keep reading
            if not chunk:
                break
            buf += chunk.decode()
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    if "event" in msg:
                        yield msg["event"]
                    # Skip ACK {"result": "subscribed"} and keep-alives {"ping": 1}
                except json.JSONDecodeError:
                    pass
    except (OSError, TimeoutError):
        pass
    finally:
        sock.close()


def call(method: str, timeout: int = _SOCKET_TIMEOUT, **params):
    """
    Call an RPC method on the daemon.

    Auto-starts the daemon if the socket is not present.
    Retries once after a start attempt.

    Args:
        method: Dot-separated RPC method, e.g. "env.get_active_database"
        timeout: Socket timeout in seconds (default 10). Use longer values
                 for known slow operations like reindexing.
        **params: Keyword arguments forwarded to the service function

    Returns:
        The deserialized result from the service

    Raises:
        RuntimeError: If the daemon returns an error response
        ConnectionError: If the daemon cannot be reached after auto-start
    """
    try:
        return _do_call(method, params, timeout=timeout)
    except (FileNotFoundError, ConnectionRefusedError):
        _start_daemon()
        try:
            return _do_call(method, params, timeout=timeout)
        except (FileNotFoundError, ConnectionRefusedError) as e:
            raise DaemonError(
                f"CC daemon unavailable: {e}\n"
                f"  Check the log for startup errors: {Constants.PATH_LOG_FILE}"
            ) from e
