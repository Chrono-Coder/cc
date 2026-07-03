"""The cc event bus — decouples core commands from feature reactions.

Lives in the **CLI process**, not the daemon: handlers run synchronously, in
priority order, and may prompt the user (the daemon can't). They write through
daemon RPC like everything else. A handler that raises is logged and skipped so
a broken plugin never breaks a core command — except :class:`EventCancelled`,
which a ``*.before`` handler raises to abort the in-progress command cleanly.

Handlers are discovered lazily on first ``emit`` — core in-tree handlers
(``cc.events.handlers``) and plugin handlers registered under the
``cc.event_handlers`` entry-point group.
"""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Callable

log = logging.getLogger("CC")

_CORE_HANDLER_PACKAGES = ["cc.events.handlers"]


class EventCancelled(Exception):
    """Raised by a ``*.before`` handler to abort the in-progress command."""


class EventBus:
    def __init__(self) -> None:
        # event -> list of (-priority, seq, handler); sorting runs higher
        # priority first, ties by registration order.
        self._handlers: dict[str, list[tuple[int, int, Callable]]] = {}
        self._seq = 0
        self._loaded = False

    def subscribe(self, event: str, handler: Callable, priority: int = 0) -> None:
        self._handlers.setdefault(event, []).append((-priority, self._seq, handler))
        self._seq += 1

    def emit(self, event: str, payload) -> None:
        """Run every handler for ``event`` in priority order.

        Re-raises :class:`EventCancelled` (intentional abort); swallows and logs
        any other handler exception so one bad handler can't break the command.
        """
        self._ensure_loaded()
        for _, _, handler in sorted(self._handlers.get(event, [])):
            try:
                handler(payload)
            except EventCancelled:
                raise
            except Exception as e:  # isolation: a broken handler never breaks core
                name = getattr(handler, "__name__", handler)
                log.warning(f"event handler {name!r} for {event!r} failed: {e}")

    def collect(self, event: str, payload) -> list:
        """Run every handler for ``event`` and aggregate their return values into
        a flat list (a handler returning a list is extended, a scalar appended,
        ``None`` skipped). Isolated like :meth:`emit` — a broken handler logs and
        contributes nothing. Use when core needs to *gather* contributions from
        handlers (e.g. extra R&D checkout failures), not just notify them.
        """
        self._ensure_loaded()
        results: list = []
        for _, _, handler in sorted(self._handlers.get(event, [])):
            try:
                r = handler(payload)
            except Exception as e:  # isolation: a broken handler never breaks core
                name = getattr(handler, "__name__", handler)
                log.warning(f"event handler {name!r} for {event!r} failed: {e}")
                continue
            if r is None:
                continue
            results.extend(r) if isinstance(r, list) else results.append(r)
        return results

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True  # set first so a handler import can't re-trigger this
        for pkg in _CORE_HANDLER_PACKAGES:
            try:
                import_module(pkg)
            except Exception as e:
                log.warning(f"Failed to import core event handlers {pkg!r}: {e}")


bus = EventBus()


def subscribe(event: str, priority: int = 0):
    """Decorator: register the function as a handler for ``event``."""

    def deco(fn: Callable) -> Callable:
        bus.subscribe(event, fn, priority)
        return fn

    return deco
