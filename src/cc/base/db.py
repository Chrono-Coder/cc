import logging
import os
import sqlite3
import threading
from contextlib import contextmanager

from cc.utils.constants import Constants
from cc.utils.errors import CCError

log = logging.getLogger("CC")

# Use threading.local() to create a thread-safe object for storing the connection.
_db_context = threading.local()


def initialize_database():
    """
    Dynamically finds all BaseEntity subclasses and creates their tables,
    then runs any pending schema migrations.
    """
    import cc.base.arm  # noqa: F401 — import side effect: registers every model class
    from cc.base.arm.common.base_entity import _entity_registry
    from cc.base.migrations import run_migrations

    log.info("Initializing database schema...")
    for entity_class in _entity_registry:
        try:
            log.debug(f"Syncing schema for {entity_class.__name__}")
            entity_class.sync_schema()
        except Exception as e:
            log.error(f"Error creating table for {entity_class.__name__}: {e}")

    run_migrations()


def _get_new_connection() -> sqlite3.Connection:
    """Internal helper to create and configure a new sqlite3 connection."""
    db_path = Constants.SQLITE_DB_PATH
    db_dir = os.path.dirname(db_path)

    if db_dir and not os.path.exists(db_dir):
        log.debug(f"Database directory not found. Creating: {db_dir}")
        os.makedirs(db_dir, exist_ok=True)

    log.debug(f"Connecting to database at: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def database_connection_manager():
    """
    A context manager to handle the database connection lifecycle.
    Usage:
        with database_connection_manager() as conn:
            # All code inside this block has access to the connection
            # via get_db_connection()
    """
    # Check if a connection is already being managed in this context
    if hasattr(_db_context, "connection") and _db_context.connection is not None:
        # If so, just yield the existing connection (allows for nested calls)
        log.debug("Using existing (nested) database connection.")
        yield _db_context.connection
        return

    conn = None
    try:
        # Acquire the resource (open the connection) and set it on the context
        conn = _get_new_connection()
        _db_context.connection = conn
        log.debug("New database connection opened and set in context.")

        # Yield the connection to the 'with' block
        yield conn

        # If the 'with' block finishes without an exception, commit.
        log.debug("Committing transaction.")
        conn.commit()

    except (CCError, SystemExit, KeyboardInterrupt):
        if conn:
            conn.rollback()
        raise
    except BaseException as e:
        log.error("An exception occurred. Rolling back transaction:", exc_info=True)
        if conn:
            conn.rollback()
        raise
    finally:
        # Always release the resource (close the connection)
        if conn:
            conn.close()
            log.debug("Database connection closed.")
        # Clear the connection from the context
        _db_context.connection = None


def get_db_connection() -> sqlite3.Connection:
    """

    Gets the currently active database connection from the context.
    This function should only be called from within a 'with database_connection_manager()' block.
    """
    if not hasattr(_db_context, "connection") or _db_context.connection is None:
        log.error("Database connection not available. get_db_connection() called outside of context.")
        raise RuntimeError(
            "Database connection not available. Ensure you are operating within a 'database_connection_manager' context."
        )
    return _db_context.connection
