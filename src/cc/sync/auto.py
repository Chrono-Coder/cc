"""
CC Sync Auto — background thread that periodically pushes/pulls with the server.

Started by the daemon on startup if CC_SERVER is configured. Runs every
SYNC_INTERVAL_MINUTES (default 5). Failures are logged and retried on
the next cycle — never interrupts normal cc operation.
"""
import logging
import os
import threading
import time

log = logging.getLogger("CC")

SYNC_INTERVAL_MINUTES = 5
_stop_event = threading.Event()


def _is_configured() -> bool:
    """Check if sync server is configured via env vars or settings."""
    if os.environ.get("CC_SERVER") and os.environ.get("CC_API_KEY"):
        return True
    try:
        from cc.base.arm.setting import Setting
        from cc.base.db import database_connection_manager
        with database_connection_manager():
            url = Setting.find_by(name="sync.server_url", limit=1)
            key = Setting.find_by(name="sync.api_key", limit=1)
            return bool(url and url.value and key and key.value)
    except Exception:
        return False


def _sync_cycle():
    """Run one push/pull cycle."""
    from cc.sync import http_client
    from cc.services import sync as sync_service
    from cc.base.db import database_connection_manager

    # Stamp any unstamped rows
    with database_connection_manager():
        sync_service.stamp_sync_ids()

    # Pull from server → push into local
    try:
        remote_data = http_client.call("sync.pull")
        changes = {t: rows for t, rows in remote_data.items() if t != "server_time"}
        total_pulled = sum(len(rows) for rows in changes.values())
        if total_pulled > 0:
            with database_connection_manager():
                result = sync_service.push(changes=changes)
            log.debug(f"Auto-sync pulled: {result['accepted']} new, {result['skipped']} skipped")
    except Exception as e:
        log.debug(f"Auto-sync pull failed: {e}")

    # Push local → server
    try:
        with database_connection_manager():
            local_data = sync_service.pull()
        changes = {t: rows for t, rows in local_data.items() if t != "server_time"}
        total_push = sum(len(rows) for rows in changes.values())
        if total_push > 0:
            result = http_client.call("sync.push", changes=changes)
            log.debug(f"Auto-sync pushed: {result['accepted']} accepted, {result['skipped']} skipped")
    except Exception as e:
        log.debug(f"Auto-sync push failed: {e}")


def _run_loop():
    """Main loop — runs sync cycles at the configured interval."""
    log.debug(f"Auto-sync thread started (interval: {SYNC_INTERVAL_MINUTES}m)")
    while not _stop_event.is_set():
        try:
            _sync_cycle()
        except Exception as e:
            log.debug(f"Auto-sync cycle error: {e}")
        _stop_event.wait(SYNC_INTERVAL_MINUTES * 60)
    log.debug("Auto-sync thread stopped")


def start():
    """Start the auto-sync background thread if configured. No-op if not."""
    if not _is_configured():
        log.debug("Auto-sync: server not configured, skipping")
        return None

    _stop_event.clear()
    thread = threading.Thread(target=_run_loop, daemon=True, name="cc-auto-sync")
    thread.start()
    log.debug("Auto-sync: background thread launched")
    return thread


def stop():
    """Signal the auto-sync thread to stop."""
    _stop_event.set()
