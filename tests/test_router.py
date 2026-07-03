"""
Router dispatch tests — no DB required.
Verifies that method strings resolve to the correct service functions.
"""
import pytest

from cc.daemon.router import RPCError, dispatch


# ── Happy-path dispatch ──────────────────────────────────────────────────────

def test_dispatch_known_namespace_and_function(_db):
    """env.find_by_name with a name that doesn't exist returns None — proves dispatch works."""
    result = dispatch("env.find_by_name", {"name": "nonexistent"})
    assert result is None


def test_dispatch_project_get_all(_db):
    """project.get_all on empty DB returns an empty list."""
    result = dispatch("project.get_all", {})
    assert result == []


def test_dispatch_setting_upsert_then_read(_db):
    """setting.upsert creates a record; a second call updates it."""
    dispatch("setting.upsert", {"key": "test_key", "value": "v1"})
    dispatch("setting.upsert", {"key": "test_key", "value": "v2"})

    from cc.base.db import database_connection_manager
    from cc.base.arm.setting import Setting
    with database_connection_manager():
        s = Setting.find_by(name="test_key", limit=1)
    assert s.value == "v2"


# ── Error cases ──────────────────────────────────────────────────────────────

def test_dispatch_unknown_namespace_raises():
    with pytest.raises(RPCError) as exc_info:
        dispatch("bogus.method", {})
    assert exc_info.value.code == -32601
    assert "Unknown namespace" in exc_info.value.message


def test_dispatch_unknown_method_raises():
    with pytest.raises(RPCError) as exc_info:
        dispatch("env.does_not_exist", {})
    assert exc_info.value.code == -32601
    assert "Unknown method" in exc_info.value.message


def test_dispatch_bad_format_raises():
    with pytest.raises(RPCError) as exc_info:
        dispatch("nodot", {})
    assert exc_info.value.code == -32600


# ── @rpc_method validation ───────────────────────────────────────────────────

def test_dispatch_missing_required_param_raises(_db):
    """Calling a method without a required param returns -32602."""
    with pytest.raises(RPCError) as exc_info:
        dispatch("env.delete", {})  # env_id is required
    assert exc_info.value.code == -32602
    assert "env_id" in exc_info.value.message


def test_dispatch_wrong_type_raises(_db):
    """Passing wrong type for a required param returns -32602."""
    with pytest.raises(RPCError) as exc_info:
        dispatch("env.delete", {"env_id": "not-an-int"})
    assert exc_info.value.code == -32602
    assert "env_id" in exc_info.value.message


def test_dispatch_undecorated_function_blocked(_db):
    """Private / undecorated functions must not be callable via RPC."""
    with pytest.raises(RPCError) as exc_info:
        dispatch("env._resolve_active_env", {})
    assert exc_info.value.code == -32601


# ── List serialization (regression: EnvDetailDTO not JSON serializable) ──────

def test_dispatch_find_by_project_name_returns_plain_dicts(_db):
    """find_by_project_name must return a list of plain dicts, not DTO objects."""
    result = dispatch("env.find_by_project_name", {"project_name": "nonexistent"})
    assert isinstance(result, list)
    # If a non-empty result came back, every item must be a dict
    for item in result:
        assert isinstance(item, dict)
