"""Daemon-side event bus: in-process handlers (the plugin seam) run on publish,
synchronously and isolated, alongside the existing SSE subscribers."""
from cc.daemon.event_bus import EventBus, EventType


def _fresh_bus():
    bus = EventBus()
    bus._loaded = True  # skip core/plugin handler discovery — test in isolation
    return bus


def test_handler_runs_with_payload():
    bus = _fresh_bus()
    got = []
    bus.on(EventType.ENV_SWITCHED, lambda p: got.append(p))
    bus.publish(EventType.ENV_SWITCHED, {"env_id": 1, "project_path": "/tmp/x"})
    assert got == [{"env_id": 1, "project_path": "/tmp/x"}]


def test_multiple_handlers_all_run():
    bus = _fresh_bus()
    hits = []
    bus.on(EventType.ENV_SWITCHED, lambda p: hits.append("a"))
    bus.on(EventType.ENV_SWITCHED, lambda p: hits.append("b"))
    bus.publish(EventType.ENV_SWITCHED, {})
    assert hits == ["a", "b"]


def test_broken_handler_is_isolated():
    bus = _fresh_bus()
    hits = []

    def boom(_):
        raise RuntimeError("broken handler")

    bus.on(EventType.ENV_SWITCHED, boom)
    bus.on(EventType.ENV_SWITCHED, lambda p: hits.append("ran"))
    bus.publish(EventType.ENV_SWITCHED, {})  # must not raise
    assert hits == ["ran"]


def test_handler_only_for_its_event():
    bus = _fresh_bus()
    hits = []
    bus.on(EventType.ENV_SWITCHED, lambda p: hits.append(1))
    bus.publish(EventType.PROJECT_CHANGED, {})
    assert hits == []


def test_sse_subscriber_still_fed():
    bus = _fresh_bus()
    q, unsub = bus.subscribe()
    try:
        bus.publish(EventType.ENV_CHANGED, {"x": 1})
        evt = q.get_nowait()
        assert evt["type"] == "env.changed" and evt["x"] == 1
    finally:
        unsub()


def test_ensure_loaded_runs_and_is_idempotent():
    # Discovery imports core handler packages + the cc.daemon_handlers entry-point
    # group without error. (intel's reindex handler now ships in cc-intel, so it's
    # only registered when that plugin is installed — not asserted here so the
    # core suite passes without the plugin.)
    bus = EventBus()
    bus._ensure_loaded()
    assert bus._loaded is True
    bus._ensure_loaded()  # idempotent — no error, no re-import
    assert bus._loaded is True
