"""Background PG metadata cache sync — periodically runs database.reconcile() so
the Database table mirrors live Postgres and readers hit SQLite only."""
import logging
import threading

log = logging.getLogger("CC")

SYNC_INTERVAL_SECONDS = 120
_stop_event = threading.Event()


def _run_loop():
    from cc.services import database

    log.debug(f"db-cache sync started (interval: {SYNC_INTERVAL_SECONDS}s)")
    while not _stop_event.is_set():
        try:
            result = database.reconcile()
            log.debug(f"db-cache reconcile: {result}")
        except Exception as e:
            # Postgres unreachable — keep the existing cache, retry next cycle.
            log.debug(f"db-cache reconcile failed: {e}")
        _stop_event.wait(SYNC_INTERVAL_SECONDS)
    log.debug("db-cache sync stopped")


def start():
    """Launch the background reconcile thread (immediate first pass)."""
    _stop_event.clear()
    thread = threading.Thread(target=_run_loop, daemon=True, name="cc-db-cache")
    thread.start()
    return thread


def stop():
    _stop_event.set()
