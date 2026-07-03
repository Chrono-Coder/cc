"""
CC Daemon EventBus — thread-safe publish/subscribe for daemon events.

Usage (publisher — called from service methods after DB commit):
    from cc.daemon.event_bus import EventType, publish
    publish(EventType.ENV_SWITCHED, {"env_id": 1, "env_name": "dev"})

Usage (subscriber — called from server.py for long-lived subscribe connections):
    from cc.daemon.event_bus import subscribe
    q, unsubscribe = subscribe()
    try:
        event = q.get(timeout=30)  # {"type": "env.switched", "env_id": 1, ...}
    finally:
        unsubscribe()
"""
import logging
import queue
import threading
from enum import Enum
from importlib import import_module

log = logging.getLogger("CC")

# Daemon-side, in-process handlers discovered from core handler packages.
# Distinct from the SSE subscribers above (those are long-lived web streams;
# these are callbacks run on publish).
_CORE_HANDLER_PACKAGES = ("cc.daemon.handlers",)


class EventType(str, Enum):
    ENV_SWITCHED = "env.switched"
    SWITCH_LOG_NEW = "switch_log.new"
    ENV_CHANGED = "env.changed"
    PROJECT_CHANGED = "project.changed"
    DAEMON_READY = "daemon.ready"


class EventBus:
    def __init__(self):
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue] = []
        self._handlers: dict[str, list] = {}  # event value → in-process callbacks
        self._loaded = False

    def publish(self, event_type: EventType, payload: dict | None = None):
        """Publish an event to all SSE subscribers (non-blocking) and run every
        registered in-process handler (synchronous, isolated)."""
        event = {"type": event_type.value, **(payload or {})}
        with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass  # Slow subscriber — drop rather than block
        self._dispatch(event_type.value, payload or {})

    def on(self, event_type: EventType, handler) -> None:
        """Register an in-process handler ``handler(payload: dict)`` for an event.
        Handlers must be non-blocking — spawn a thread for heavy work (see the
        reindex handler) so a publish never stalls the publishing service."""
        with self._lock:
            self._handlers.setdefault(event_type.value, []).append(handler)

    def _dispatch(self, event_value: str, payload: dict) -> None:
        self._ensure_loaded()
        with self._lock:
            handlers = list(self._handlers.get(event_value, []))
        for fn in handlers:
            try:  # isolation: a broken handler never breaks the publisher
                fn(payload)
            except Exception as e:
                name = getattr(fn, "__name__", fn)
                log.warning(f"daemon event handler {name!r} for {event_value!r} failed: {e}")

    def _ensure_loaded(self) -> None:
        """Import core daemon-handler packages + plugin `cc.daemon_handlers`
        entry points so their @on_event registrations run (lazy, once)."""
        if self._loaded:
            return
        self._loaded = True
        for pkg in _CORE_HANDLER_PACKAGES:
            try:
                import_module(pkg)
            except Exception as e:
                log.warning(f"Failed to import core daemon handlers {pkg!r}: {e}")

    def subscribe(self) -> tuple[queue.Queue, callable]:
        """
        Register a new subscriber queue.

        Returns (queue, unsubscribe_fn). Caller must call unsubscribe_fn()
        when done to remove the queue from the bus.
        """
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)

        def unsubscribe():
            with self._lock:
                try:
                    self._subscribers.remove(q)
                except ValueError:
                    pass

        return q, unsubscribe


# Module-level singleton — imported by services and server
_bus = EventBus()


def publish(event_type: EventType, payload: dict | None = None):
    """Publish to the module-level EventBus singleton."""
    _bus.publish(event_type, payload)


def subscribe() -> tuple[queue.Queue, callable]:
    """Subscribe to the module-level EventBus singleton (SSE stream)."""
    return _bus.subscribe()


def on(event_type: EventType, handler) -> None:
    """Register an in-process handler on the singleton bus."""
    _bus.on(event_type, handler)


def on_event(event_type: EventType):
    """Decorator: register the function as a daemon-side handler for an event.

        @on_event(EventType.ENV_SWITCHED)
        def reindex(payload): ...
    """
    def deco(fn):
        _bus.on(event_type, fn)
        return fn
    return deco
