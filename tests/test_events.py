"""Event bus mechanics (priority / isolation / cancel) + the in-core timesheet
handler. No real DB — `_db` redirects the ORM to a temp SQLite; the daemon write
is stubbed.
"""
import pytest

from cc.events.bus import EventBus, EventCancelled


def _fresh_bus():
    """A bus that skips discovery — exercises the mechanism in isolation."""
    b = EventBus()
    b._loaded = True
    return b


def _raise(exc):
    def _h(_event):
        raise exc
    return _h


# ── mechanics ────────────────────────────────────────────────────────────

def test_emit_calls_handler_with_payload():
    b = _fresh_bus()
    seen = []
    b.subscribe("x", seen.append)
    b.emit("x", {"k": 1})
    assert seen == [{"k": 1}]


def test_priority_runs_high_first():
    b = _fresh_bus()
    order = []
    b.subscribe("x", lambda e: order.append("low"), priority=0)
    b.subscribe("x", lambda e: order.append("high"), priority=10)
    b.subscribe("x", lambda e: order.append("mid"), priority=5)
    b.emit("x", None)
    assert order == ["high", "mid", "low"]


# ── collect (the collecting hook — handlers contribute return values) ──────

def test_collect_aggregates_returns():
    b = _fresh_bus()
    b.subscribe("c", lambda e: ["a", "b"])   # list → extended
    b.subscribe("c", lambda e: "scalar")      # scalar → appended
    b.subscribe("c", lambda e: None)          # None → skipped
    assert b.collect("c", None) == ["a", "b", "scalar"]


def test_collect_isolates_broken_handler():
    b = _fresh_bus()
    b.subscribe("c", _raise(RuntimeError("boom")))
    b.subscribe("c", lambda e: ["ok"])
    assert b.collect("c", None) == ["ok"]  # broken contributes nothing, never raises


def test_collect_empty_with_no_handlers():
    assert _fresh_bus().collect("none", None) == []


def test_same_priority_keeps_registration_order():
    b = _fresh_bus()
    order = []
    b.subscribe("x", lambda e: order.append(1))
    b.subscribe("x", lambda e: order.append(2))
    b.emit("x", None)
    assert order == [1, 2]


def test_broken_handler_is_isolated():
    b = _fresh_bus()
    ran = []
    b.subscribe("x", _raise(RuntimeError("boom")))
    b.subscribe("x", lambda e: ran.append(True))
    b.emit("x", None)  # must NOT raise
    assert ran == [True]


def test_cancel_propagates_and_stops_the_chain():
    b = _fresh_bus()
    ran = []
    b.subscribe("x", _raise(EventCancelled()), priority=10)
    b.subscribe("x", lambda e: ran.append(True), priority=0)
    with pytest.raises(EventCancelled):
        b.emit("x", None)
    assert ran == []  # cancel aborted before the lower-priority handler ran


def test_emit_with_no_handlers_is_noop():
    _fresh_bus().emit("nobody-home", None)


# ── core handler discovery + the migrated timesheet handler ──────────────

def test_first_emit_loads_core_handlers(_db):
    from cc.base.db import database_connection_manager
    from cc.events import bus
    from cc.events.events import SwitchEvent
    with database_connection_manager():
        bus.emit("switch.before", SwitchEvent())  # empty temp DB → handler no-ops
    assert "switch.before" in bus._handlers
    assert any(getattr(h, "__name__", "") == "flag_long_session"
               for _, _, h in bus._handlers["switch.before"])


def _seed_long_session(env_id):
    from datetime import datetime, timedelta, timezone

    from cc.base.arm import SwitchLog
    from cc.base.arm.setting import Setting
    from cc.base.db import database_connection_manager
    old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    with database_connection_manager():
        SwitchLog.create({"environment_id": env_id, "switched_at": old})
        Setting.create({"name": "timesheet_flag_threshold", "value": "30"})


def _make_env():
    from cc.services import environment, project
    proj = project.create("acme")
    return environment.create(
        name="staging", project_id=proj["id"], version_name="17.0", version_path="/tmp/v17",
        project_path="/tmp/acme", github_url="", branch_name="main",
        database_name="acme", module_names=[],
    )


def test_timesheet_handler_cancels_when_declined(_db, monkeypatch):
    from cc.events.events import SwitchEvent
    from cc.events.handlers import timesheet as h
    from cc.utils.prompter.prompter import Prompter

    env = _make_env()
    _seed_long_session(env["id"])
    monkeypatch.setattr(h, "call", lambda *a, **k: None)                 # no daemon write
    monkeypatch.setattr(Prompter, "prompt_confirm", lambda *a, **k: False)  # user declines

    from cc.base.db import database_connection_manager
    with database_connection_manager():
        with pytest.raises(EventCancelled):
            h.flag_long_session(SwitchEvent())


def test_timesheet_handler_proceeds_when_accepted(_db, monkeypatch):
    from cc.events.events import SwitchEvent
    from cc.events.handlers import timesheet as h
    from cc.utils.prompter.prompter import Prompter

    env = _make_env()
    _seed_long_session(env["id"])
    monkeypatch.setattr(h, "call", lambda *a, **k: None)
    monkeypatch.setattr(Prompter, "prompt_confirm", lambda *a, **k: True)   # user accepts

    from cc.base.db import database_connection_manager
    with database_connection_manager():
        h.flag_long_session(SwitchEvent())  # must not raise


def test_timesheet_handler_noop_when_no_history(_db):
    from cc.base.db import database_connection_manager
    from cc.events.events import SwitchEvent
    from cc.events.handlers import timesheet as h
    with database_connection_manager():
        h.flag_long_session(SwitchEvent())  # empty DB → returns early, no raise
