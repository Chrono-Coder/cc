"""
Shared test fixtures.

All tests that touch the service/ORM layer use the `db` fixture, which redirects
every database_connection_manager() call to a fresh per-test SQLite temp file.
The real ~/.cc-cli/cc_cli.db is never touched.
"""
import sqlite3

import pytest


@pytest.fixture
def _db(tmp_path, monkeypatch):
    """
    Redirect all DB access to a fresh temp SQLite file for this test.

    Patches cc.base.db._get_new_connection so every service call that opens a
    database_connection_manager() uses the temp file instead of the real DB.
    """
    db_file = tmp_path / "test_cc.db"

    def _temp_connection():
        conn = sqlite3.connect(str(db_file))
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("cc.base.db._get_new_connection", _temp_connection)

    # Import all entities to populate _entity_registry before initialising schema
    from cc.base.arm import (  # noqa: F401
        AppState,
        Backup,
        Database,
        Device,
        DevicePath,
        Environment,
        Module,
        Project,
        Setting,
        SwitchLog,
        Version,
        Workspace,
    )

    from cc.base.db import database_connection_manager, initialize_database

    with database_connection_manager():
        initialize_database()

    yield str(db_file)
