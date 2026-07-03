"""Opportunistic intel reindex after a switch — a daemon-side event handler.

In-core for now; when intel is extracted this module moves into the plugin and
registers via the ``cc.daemon_handlers`` entry-point group (no core change). The
switch service just publishes ``ENV_SWITCHED``; it no longer knows about intel.
"""
import logging
import threading

from cc.daemon.event_bus import EventType, on_event

log = logging.getLogger("CC")


@on_event(EventType.ENV_SWITCHED)
def reindex_on_switch(payload: dict) -> None:
    """Fire-and-forget: index the switched-to project in a background thread so
    the switch returns immediately. No-op without a project_path."""
    project_path = payload.get("project_path")
    if not project_path:
        return
    threading.Thread(
        target=_maybe_opportunistic_reindex, args=(project_path,), daemon=True
    ).start()


def _maybe_opportunistic_reindex(project_path: str) -> None:
    """Owns its own DB connection. No-op if no enabled Repository is registered
    at project_path or it was indexed within the last hour. Errors are logged,
    never raised — must not affect the user's switch UX."""
    try:
        from datetime import datetime, timedelta, timezone
        from pathlib import Path

        from cc.base.arm import Repository
        from cc.base.arm.setting import Setting
        from cc.base.db import database_connection_manager
        from cc.intel.indexer import index_repository

        project_path = str(Path(project_path).resolve())

        with database_connection_manager():
            opt_out = Setting.find_by(name="intel.auto_reindex", limit=1)
            if opt_out and (opt_out.value or "").lower() in {"false", "0", "no", "off"}:
                return

            repo = Repository.find_by(path=project_path, limit=1)
            if not repo or not repo.enabled:
                return

            if repo.last_indexed_at:
                try:
                    last = datetime.fromisoformat(repo.last_indexed_at)
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) - last < timedelta(hours=1):
                        return
                except (ValueError, TypeError):
                    pass

            index_repository(repo, full=False)
    except Exception:
        log.debug("opportunistic reindex failed", exc_info=True)
