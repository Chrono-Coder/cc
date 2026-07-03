"""
Sync service tests — vertical spike.

Proves: device registration, sync_id stamping, push/pull between two databases,
and device path linking.
"""
import sqlite3
import uuid

import pytest

from cc.base.db import database_connection_manager


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_project(name="test_project"):
    from cc.services import project
    return project.create(name)


def _create_env(project_id, name="test_env"):
    from cc.services import environment
    return environment.create(
        name=name,
        project_id=project_id,
        version_name="17.0",
        version_path="/tmp/v17",
        project_path="/tmp/myproject",
        github_url="https://github.com/test/repo",
        branch_name="main",
        database_name="test_db",
        module_names=["sale"],
    )


# ── Device registration ─────────────────────────────────────────────────────

def test_register_device_creates_device(_db):
    from cc.services import sync

    with database_connection_manager():
        result = sync.register_device(name="macbook")
    assert result["name"] == "macbook"
    assert result["api_key"]
    assert result["id"] > 0


def test_register_device_idempotent(_db):
    from cc.services import sync

    with database_connection_manager():
        first = sync.register_device(name="macbook")
        second = sync.register_device(name="macbook")
    assert first["api_key"] == second["api_key"]
    assert first["id"] == second["id"]


# ── Sync ID stamping ────────────────────────────────────────────────────────

def test_stamp_sync_ids_on_existing_rows(_db):
    from cc.services import sync

    with database_connection_manager():
        proj = _create_project("stamp_test")
        _create_env(proj["id"], "env_stamp")

    with database_connection_manager():
        result = sync.stamp_sync_ids()
    assert result["stamped"] >= 2  # at least project + environment

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        env_row = conn.execute("SELECT sync_id FROM environment WHERE name = 'env_stamp'").fetchone()
        assert env_row["sync_id"] is not None
        # Verify it's a valid UUID
        uuid.UUID(env_row["sync_id"])


def test_stamp_idempotent(_db):
    from cc.services import sync

    with database_connection_manager():
        _create_project("idem_test")

    with database_connection_manager():
        first = sync.stamp_sync_ids()
    with database_connection_manager():
        second = sync.stamp_sync_ids()
    assert second["stamped"] == 0  # all already stamped


# ── Pull ─────────────────────────────────────────────────────────────────────

def test_pull_returns_stamped_rows(_db):
    from cc.services import sync

    with database_connection_manager():
        proj = _create_project("pull_test")
        _create_env(proj["id"], "env_pull")

    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        result = sync.pull()
    assert "environment" in result
    assert "project" in result
    assert "server_time" in result
    env_names = [r["name"] for r in result["environment"]]
    assert "env_pull" in env_names


def test_pull_with_since_filters(_db):
    from cc.services import sync

    with database_connection_manager():
        proj = _create_project("since_test")
        _create_env(proj["id"], "env_since")

    with database_connection_manager():
        sync.stamp_sync_ids()

    # Pull with a future timestamp — should return nothing
    with database_connection_manager():
        result = sync.pull(since="2099-01-01T00:00:00")
    assert len(result["environment"]) == 0
    assert len(result["project"]) == 0


# ── Push ─────────────────────────────────────────────────────────────────────

def test_push_inserts_new_rows(_db):
    from cc.services import sync

    # Ensure the project table has the sync_id column available
    with database_connection_manager():
        _create_project("existing")

    incoming = {
        "project": [
            {"name": "remote_project", "sync_id": str(uuid.uuid4()), "synced_at": "2026-01-01T00:00:00"},
        ],
        "environment": [],
    }

    with database_connection_manager():
        result = sync.push(changes=incoming)
    assert result["accepted"] == 1
    assert result["skipped"] == 0

    # Verify it landed
    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT name FROM project WHERE name = 'remote_project'").fetchone()
        assert row is not None


def test_push_skips_duplicates(_db):
    from cc.services import sync

    sid = str(uuid.uuid4())
    incoming = {
        "project": [
            {"name": "dup_project", "sync_id": sid, "synced_at": "2026-01-01T00:00:00"},
        ],
    }

    with database_connection_manager():
        sync.push(changes=incoming)
    with database_connection_manager():
        result = sync.push(changes=incoming)
    assert result["skipped"] == 1
    assert result["accepted"] == 0


def test_push_skips_rows_without_sync_id(_db):
    from cc.services import sync

    incoming = {
        "project": [
            {"name": "no_sync_id_project"},
        ],
    }

    with database_connection_manager():
        result = sync.push(changes=incoming)
    assert result["skipped"] == 1
    assert result["accepted"] == 0


# ── Device path linking ──────────────────────────────────────────────────────

def test_link_project_to_device(_db):
    from cc.services import sync

    with database_connection_manager():
        sync.register_device(name="macbook")
        _create_project("link_test")

    with database_connection_manager():
        result = sync.link_project(
            device_name="macbook",
            project_name="link_test",
            local_path="/Users/peter/dev/link_test",
        )
    assert result["device"] == "macbook"
    assert result["project"] == "link_test"
    assert result["local_path"] == "/Users/peter/dev/link_test"
    assert result["updated"] is False


def test_link_project_update_path(_db):
    from cc.services import sync

    with database_connection_manager():
        sync.register_device(name="macbook")
        _create_project("relink_test")

    with database_connection_manager():
        sync.link_project(device_name="macbook", project_name="relink_test", local_path="/old/path")

    with database_connection_manager():
        result = sync.link_project(device_name="macbook", project_name="relink_test", local_path="/new/path")
    assert result["updated"] is True
    assert result["local_path"] == "/new/path"


# ── Sync status ──────────────────────────────────────────────────────────────

def test_sync_status_shows_pending(_db):
    from cc.services import sync

    with database_connection_manager():
        proj = _create_project("status_test")
        _create_env(proj["id"], "env_status")

    # Stamp gives sync_id but no synced_at → pending
    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        result = sync.status()
    assert result["pending"]["environment"] >= 1
    assert result["pending"]["project"] >= 1


# ── End-to-end: two-database sync ───────────────────────────────────────────

def test_full_sync_between_two_databases(_db, tmp_path, monkeypatch):
    """Simulate syncing from device A's database to device B's database."""
    from cc.services import sync

    # ── Device A: create data and stamp ──
    with database_connection_manager():
        proj = _create_project("shared_project")
        _create_env(proj["id"], "shared_env")
    with database_connection_manager():
        sync.stamp_sync_ids()
    with database_connection_manager():
        pulled = sync.pull()

    # ── Switch to Device B's database ──
    db_file_b = tmp_path / "device_b.db"

    def _temp_connection_b():
        conn = sqlite3.connect(str(db_file_b))
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("cc.base.db._get_new_connection", _temp_connection_b)

    from cc.base.db import initialize_database
    with database_connection_manager():
        initialize_database()

    # ── Push A's data into B ──
    changes = {table: rows for table, rows in pulled.items() if table != "server_time"}
    with database_connection_manager():
        result = sync.push(changes=changes)

    assert result["accepted"] >= 2  # project + environment at minimum

    # ── Verify B has the data ──
    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT name FROM project WHERE name = 'shared_project'").fetchone()
        assert row is not None
        env_row = conn.execute("SELECT name FROM environment WHERE name = 'shared_env'").fetchone()
        assert env_row is not None


# ── FK resolution across databases ──────────────────────────────────────────

def test_push_resolves_fks_by_natural_key(_db, tmp_path, monkeypatch):
    """FKs must resolve by natural key, not by copying raw integer IDs."""
    from cc.services import sync

    # ── Device A: create version + project + env ──
    with database_connection_manager():
        proj = _create_project("fk_project")
        _create_env(proj["id"], "fk_env")

    with database_connection_manager():
        sync.stamp_sync_ids()
    with database_connection_manager():
        pulled = sync.pull()

    # Verify pull enriched FK refs
    env_rows = pulled["environment"]
    fk_env = [e for e in env_rows if e["name"] == "fk_env"][0]
    assert "_fk_project_id" in fk_env
    assert fk_env["_fk_project_id"] == "fk_project"

    # ── Device B: fresh database with the SAME project pre-existing ──
    db_file_b = tmp_path / "device_b_fk.db"

    def _temp_connection_b():
        conn = sqlite3.connect(str(db_file_b))
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr("cc.base.db._get_new_connection", _temp_connection_b)

    from cc.base.db import initialize_database
    with database_connection_manager():
        initialize_database()

    # Create a project with the same name on B — it will get a DIFFERENT id
    with database_connection_manager():
        _create_project("fk_project")

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        b_project = conn.execute("SELECT id FROM project WHERE name = 'fk_project'").fetchone()
        b_project_id = b_project["id"]

    # Push A's data into B (skip project since it exists, but env should land)
    changes = {table: rows for table, rows in pulled.items() if table != "server_time"}
    with database_connection_manager():
        result = sync.push(changes=changes)

    # The environment should have been inserted with B's project_id, not A's
    with database_connection_manager():
        conn = get_db_connection()
        env = conn.execute("SELECT project_id FROM environment WHERE name = 'fk_env'").fetchone()
        assert env is not None
        assert env["project_id"] == b_project_id


# ── New syncable tables ─────────────────────────────────────────────────────

def test_stamp_covers_new_tables(_db):
    """stamp_sync_ids should cover version, database, setting tables."""
    from cc.services import sync

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        # Create version, database, setting rows
        conn.execute("INSERT INTO version (name, path) VALUES ('18.0', '/tmp/v18')")
        conn.execute("INSERT INTO database (name) VALUES ('test_db_stamp')")
        conn.execute("INSERT INTO setting (name, value) VALUES ('test.key', 'test_val')")

    with database_connection_manager():
        result = sync.stamp_sync_ids()
    assert result["stamped"] >= 3

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        for table in ["version", "database", "setting"]:
            row = conn.execute(f"SELECT sync_id FROM {table} LIMIT 1").fetchone()
            assert row["sync_id"] is not None


def test_pull_includes_new_tables(_db):
    """pull should return version, database, setting records."""
    from cc.services import sync

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        conn.execute("INSERT INTO version (name, path) VALUES ('16.0', '/tmp/v16')")
        conn.execute("INSERT INTO database (name) VALUES ('pull_db_test')")
        conn.execute("INSERT INTO setting (name, value) VALUES ('pull.color', 'val')")

    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        result = sync.pull()

    assert "version" in result
    assert "database" in result
    assert "setting" in result
    assert any(r["name"] == "16.0" for r in result["version"])
    assert any(r["name"] == "pull_db_test" for r in result["database"])
    assert any(r["name"] == "pull.color" for r in result["setting"])


def test_pull_excludes_secret_settings(_db):
    """pull should never include sync credentials."""
    from cc.services import sync

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        conn.execute("INSERT INTO setting (name, value) VALUES ('sync.api_key', 'key123')")
        conn.execute("INSERT INTO setting (name, value) VALUES ('sync.server_url', 'https://example.com')")
        conn.execute("INSERT INTO setting (name, value) VALUES ('safe.setting', 'visible')")

    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        result = sync.pull()

    setting_names = [r["name"] for r in result["setting"]]
    assert "sync.api_key" not in setting_names
    assert "sync.server_url" not in setting_names
    assert "safe.setting" in setting_names


def test_pull_excludes_credential_shaped_settings(_db):
    """Any credential-shaped setting name (github_pat, *.token, pg.connection)
    is excluded from pull, not just the explicit sync.* pair."""
    from cc.services import sync

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        for name in ("github_pat", "some.token", "api_key", "pg.connection"):
            conn.execute("INSERT INTO setting (name, value) VALUES (?, 'secret')", (name,))
        conn.execute("INSERT INTO setting (name, value) VALUES ('theme', 'dark')")

    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        result = sync.pull()

    setting_names = [r["name"] for r in result["setting"]]
    assert "theme" in setting_names
    for name in ("github_pat", "some.token", "api_key", "pg.connection"):
        assert name not in setting_names


def test_push_rejects_secret_settings(_db):
    """A pushed secret setting must not be inserted: a hostile peer can't
    plant credentials that then propagate to every pulling device."""
    from cc.services import sync

    with database_connection_manager():
        result = sync.push(changes={
            "setting": [
                {"sync_id": "s-1", "name": "github_pat", "value": "evil"},
                {"sync_id": "s-2", "name": "theme", "value": "dark"},
            ]
        })

    assert result["accepted"] == 1
    assert result["skipped"] == 1
    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        rows = conn.execute("SELECT name FROM setting").fetchall()
    names = [r["name"] for r in rows]
    assert "theme" in names
    assert "github_pat" not in names


def test_push_whitelists_columns(_db):
    """Row keys from the remote client that aren't real columns are dropped
    (column names can't be parameterized, so this is the injection guard)."""
    from cc.services import sync

    with database_connection_manager():
        result = sync.push(changes={
            "setting": [{
                "sync_id": "s-3",
                "name": "safe.entry",
                "value": "v",
                "value); DROP TABLE setting; --": "boom",
                "not_a_column": "x",
            }]
        })

    assert result["accepted"] == 1
    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT name, value FROM setting WHERE name = 'safe.entry'").fetchone()
    assert row is not None
    assert row["value"] == "v"


def test_http_server_method_allowlist():
    """Only push/pull are network-callable: register_device returns API keys
    and must stay local-only."""
    from cc.sync.http_server import ALLOWED_METHODS

    assert ALLOWED_METHODS == {"sync.push", "sync.pull"}
    assert "sync.register_device" not in ALLOWED_METHODS


# ── synced_at stamping (status accuracy + incremental pull) ──────────────────

def test_push_stamps_synced_at_on_ingest(_db):
    """Ingested rows get synced_at so the receiver doesn't report them pending."""
    from cc.services import sync

    incoming = {
        "project": [
            {"name": "ingested_proj", "sync_id": str(uuid.uuid4())},  # no synced_at supplied
        ],
    }
    with database_connection_manager():
        sync.push(changes=incoming)

    with database_connection_manager():
        from cc.base.db import get_db_connection
        conn = get_db_connection()
        row = conn.execute("SELECT synced_at FROM project WHERE name = 'ingested_proj'").fetchone()
        assert row["synced_at"] is not None

    # And it must not show up as pending.
    with database_connection_manager():
        result = sync.status()
    assert result["pending"]["project"] == 0


def test_mark_synced_clears_pending(_db):
    """After a push, mark_synced stamps stamped-but-unsynced rows so status is truthful."""
    from cc.services import sync

    with database_connection_manager():
        proj = _create_project("marksync_test")
        _create_env(proj["id"], "env_marksync")
    with database_connection_manager():
        sync.stamp_sync_ids()

    with database_connection_manager():
        before = sync.status()
    assert before["pending"]["project"] >= 1
    assert before["pending"]["environment"] >= 1

    with database_connection_manager():
        marked = sync.mark_synced()
    assert marked["marked"] >= 2

    with database_connection_manager():
        after = sync.status()
    assert after["pending"]["project"] == 0
    assert after["pending"]["environment"] == 0


def test_mark_synced_idempotent(_db):
    """A second mark_synced marks nothing — there's nothing left unsynced."""
    from cc.services import sync

    with database_connection_manager():
        _create_project("marktwice")
    with database_connection_manager():
        sync.stamp_sync_ids()
    with database_connection_manager():
        sync.mark_synced()
    with database_connection_manager():
        second = sync.mark_synced()
    assert second["marked"] == 0


def test_synced_at_enables_incremental_pull(_db):
    """A row marked synced is visible to pull(since=earlier), invisible to pull(since=later)."""
    from cc.services import sync

    with database_connection_manager():
        _create_project("incr_proj")
    with database_connection_manager():
        sync.stamp_sync_ids()
    with database_connection_manager():
        sync.mark_synced(timestamp="2026-06-01T12:00:00")

    with database_connection_manager():
        early = sync.pull(since="2026-01-01T00:00:00")
    assert any(r["name"] == "incr_proj" for r in early["project"])

    with database_connection_manager():
        late = sync.pull(since="2026-12-31T00:00:00")
    assert not any(r["name"] == "incr_proj" for r in late["project"])
