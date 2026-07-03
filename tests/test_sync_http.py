"""
Sync HTTP transport tests — spins up the sync server in a thread,
hits it with urllib, validates auth + dispatch + error handling.
"""
import json
import threading
import time
import urllib.request
import urllib.error
import uuid

import pytest

from cc.base.db import database_connection_manager


@pytest.fixture
def sync_server(_db):
    """Start the sync HTTP server on a random port, yield the base URL, shut down after."""
    from cc.sync.http_server import SyncHandler, SyncServer

    server = SyncServer(("127.0.0.1", 0), SyncHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


@pytest.fixture
def device_key(_db):
    """Register a device and return its API key."""
    from cc.services import sync
    with database_connection_manager():
        result = sync.register_device(name="test_device")
    return result["api_key"]


def _rpc(base_url, method, params=None, api_key=None, encrypted=False):
    """Make a JSON-RPC call to the sync server."""
    url = f"{base_url}/rpc"
    body = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": 1}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    if encrypted and api_key:
        from cc.sync.crypto import encrypt, is_encrypted, decrypt
        body = encrypt(body, api_key)

    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            result = json.loads(resp.read().decode())
            if encrypted and api_key:
                from cc.sync.crypto import is_encrypted, decrypt
                if is_encrypted(result):
                    result = decrypt(result, api_key)
            return resp.status, result
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


# ── Health endpoint ──────────────────────────────────────────────────────────

def test_health_endpoint(sync_server):
    req = urllib.request.Request(f"{sync_server}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
    assert data["status"] == "ok"


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_missing_auth_returns_401(sync_server):
    status, body = _rpc(sync_server, "sync.status")
    assert status == 401


def test_invalid_key_returns_403(sync_server):
    status, body = _rpc(sync_server, "sync.status", api_key="bad-key")
    assert status == 403


def test_valid_key_succeeds(sync_server, device_key):
    status, body = _rpc(sync_server, "sync.pull", api_key=device_key)
    assert status == 200
    assert "result" in body
    assert "server_time" in body["result"]


# ── Method restriction ───────────────────────────────────────────────────────

def test_non_sync_namespace_blocked(sync_server, device_key):
    status, body = _rpc(sync_server, "env.find_by_name", params={"name": "x"}, api_key=device_key)
    assert status == 403
    assert "not allowed" in body["error"]["message"]


def test_project_namespace_blocked(sync_server, device_key):
    status, body = _rpc(sync_server, "project.create", params={"name": "x"}, api_key=device_key)
    assert status == 403


def test_local_only_sync_methods_blocked(sync_server, device_key):
    """Only push/pull are network-callable: register_device would return API
    keys, and status/stamp/link are local bookkeeping."""
    for method in ("sync.register_device", "sync.status", "sync.stamp_sync_ids", "sync.link_project"):
        status, body = _rpc(sync_server, method, params={}, api_key=device_key)
        assert status == 403, f"{method} should be blocked over HTTP"
        assert "not allowed" in body["error"]["message"]


# ── Full push/pull over HTTP ─────────────────────────────────────────────────

def test_push_and_pull_over_http(sync_server, device_key):
    sid = str(uuid.uuid4())
    push_data = {
        "project": [
            {"name": "http_project", "sync_id": sid, "synced_at": "2026-05-01T00:00:00"},
        ],
    }

    # Push
    status, body = _rpc(sync_server, "sync.push", params={"changes": push_data}, api_key=device_key)
    assert status == 200
    assert body["result"]["accepted"] == 1

    # Pull
    status, body = _rpc(sync_server, "sync.pull", api_key=device_key)
    assert status == 200
    project_names = [r["name"] for r in body["result"]["project"]]
    assert "http_project" in project_names


def test_stamp_stays_local(sync_server, device_key, _db):
    """stamp_sync_ids is local bookkeeping: blocked over HTTP, works in-process."""
    from cc.services import project, sync
    with database_connection_manager():
        project.create("stamp_http_test")

    status, _body = _rpc(sync_server, "sync.stamp_sync_ids", api_key=device_key)
    assert status == 403

    with database_connection_manager():
        result = sync.stamp_sync_ids()
    assert result["stamped"] >= 1


# ── Error handling ───────────────────────────────────────────────────────────

def test_malformed_json_returns_400(sync_server, device_key):
    url = f"{sync_server}/rpc"
    req = urllib.request.Request(
        url, data=b"not json",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {device_key}"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected error"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_404_on_unknown_path(sync_server):
    req = urllib.request.Request(f"{sync_server}/unknown")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected 404"
    except urllib.error.HTTPError as e:
        assert e.code == 404


# ── Encrypted transport ─────────────────────────────────────────────────────

def test_encrypted_push_and_pull(sync_server, device_key):
    sid = str(uuid.uuid4())
    push_data = {
        "project": [
            {"name": "encrypted_project", "sync_id": sid, "synced_at": "2026-05-01T00:00:00"},
        ],
    }

    status, body = _rpc(sync_server, "sync.push", params={"changes": push_data}, api_key=device_key, encrypted=True)
    assert status == 200
    assert body["result"]["accepted"] == 1

    status, body = _rpc(sync_server, "sync.pull", api_key=device_key, encrypted=True)
    assert status == 200
    project_names = [r["name"] for r in body["result"]["project"]]
    assert "encrypted_project" in project_names


def test_encrypted_pull(sync_server, device_key):
    status, body = _rpc(sync_server, "sync.pull", api_key=device_key, encrypted=True)
    assert status == 200
    assert "server_time" in body["result"]


def test_wrong_key_cannot_decrypt(sync_server, device_key):
    from cc.sync.crypto import encrypt
    body = {"jsonrpc": "2.0", "method": "sync.status", "params": {}, "id": 1}
    body = encrypt(body, "wrong-key-not-the-real-one")

    url = f"{sync_server}/rpc"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {device_key}"}
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        urllib.request.urlopen(req, timeout=5)
        assert False, "Expected error"
    except urllib.error.HTTPError as e:
        assert e.code == 400


def test_crypto_round_trip():
    from cc.sync.crypto import encrypt, decrypt, is_encrypted
    key = "test-api-key-12345"
    payload = {"method": "sync.push", "params": {"changes": {"project": [{"name": "x"}]}}}
    envelope = encrypt(payload, key)
    assert is_encrypted(envelope)
    assert "method" not in envelope
    restored = decrypt(envelope, key)
    assert restored == payload
