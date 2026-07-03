"""
PG metadata cache (P0): database.reconcile() mirrors live Postgres into the
Database table so readers never block on psql. We stub the pg service so the
test never touches a real Postgres.
"""
import pytest

from cc.base.arm.database import Database
from cc.base.db import database_connection_manager
from cc.services import database, pg


def _stub_pg(monkeypatch, names, sizes=None, logins=None):
    sizes = sizes or {}
    logins = logins or {}
    monkeypatch.setattr(pg, "list_databases", lambda: list(names))
    monkeypatch.setattr(
        pg, "get_db_stats",
        lambda: [{"datname": n, "size_bytes": sizes.get(n)} for n in names],
    )
    monkeypatch.setattr(pg, "get_last_logins", lambda db_names: {n: logins.get(n, {"last_login": None, "is_odoo": False}) for n in db_names})


def _rows():
    with database_connection_manager():
        return {d.name: d for d in Database.find_by()}


def test_run_sql_routes_to_docker(monkeypatch):
    from cc.services import pg_docker
    pg._backend_cache = None
    monkeypatch.setattr(pg, "_backend", lambda: "docker")
    seen = {}
    monkeypatch.setattr(pg_docker, "exec_sql", lambda sql, db="postgres": seen.update(sql=sql, db=db))
    pg.run_sql("SELECT 1", db="x")
    assert seen == {"sql": "SELECT 1", "db": "x"}
    pg._backend_cache = None


def test_load_dump_routes_to_docker(monkeypatch):
    from cc.services import pg_docker
    pg._backend_cache = None
    monkeypatch.setattr(pg, "_backend", lambda: "docker")
    seen = {}
    monkeypatch.setattr(pg_docker, "load_dump", lambda db, path: seen.update(db=db, path=path))
    pg.load_dump("d", "/tmp/x.sql")
    assert seen == {"db": "d", "path": "/tmp/x.sql"}
    pg._backend_cache = None


def test_init_from_dump_loads_and_caches(_db, monkeypatch):
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import database

    sqls, loads = [], []
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": sqls.append(sql))
    monkeypatch.setattr(pg, "load_dump", lambda db, path: loads.append((db, path)))

    database.init_from_dump("fresh", "/tmp/dump.sql", "/tmp/clean.sql")

    assert any('DROP DATABASE IF EXISTS "fresh"' in s for s in sqls)
    assert any('CREATE DATABASE "fresh"' in s for s in sqls)
    assert ("fresh", "/tmp/dump.sql") in loads and ("fresh", "/tmp/clean.sql") in loads
    with database_connection_manager():
        assert Database.find_by(name="fresh", limit=1)


def test_init_from_dump_terminates_sessions_before_drop(_db, monkeypatch):
    """Regression: a live session must not block the drop. init (and copy/restore,
    via the shared helper) terminate backends on the target *before* DROP DATABASE,
    so `cc initdb` no longer fails with 'database is being accessed by other users'.
    """
    from cc.services import database

    sqls = []
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": sqls.append(sql))
    monkeypatch.setattr(pg, "load_dump", lambda db, path: None)

    database.init_from_dump("makain-18-19", "/tmp/dump.sql")

    term_idx = next(i for i, s in enumerate(sqls)
                    if "pg_terminate_backend" in s and "makain-18-19" in s)
    drop_idx = next(i for i, s in enumerate(sqls)
                    if "DROP DATABASE" in s and "makain-18-19" in s)
    assert term_idx < drop_idx  # terminate must precede the drop


def test_copy_creates_template_and_caches(_db, monkeypatch):
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import database

    sqls = []
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": sqls.append(sql))
    result = database.copy("mydb")

    assert result == {"src": "mydb", "dest": "mydb-CC-COPY"}
    assert any("DROP DATABASE" in s and "mydb-CC-COPY" in s for s in sqls)
    assert any('CREATE DATABASE "mydb-CC-COPY" WITH TEMPLATE "mydb"' in s for s in sqls)
    with database_connection_manager():
        assert Database.find_by(name="mydb-CC-COPY", limit=1)


def test_restore_recreates_from_template(_db, monkeypatch):
    from cc.services import database

    sqls = []
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": sqls.append(sql))
    monkeypatch.setattr(pg, "database_exists", lambda name: True)
    database.restore("mydb")
    assert any('DROP DATABASE IF EXISTS "mydb"' in s for s in sqls)
    assert any('CREATE DATABASE "mydb" WITH TEMPLATE "mydb-CC-COPY"' in s for s in sqls)


def test_restore_aborts_without_dropping_when_template_missing(_db, monkeypatch):
    """Safety: a missing template must never let restore drop the live DB first."""
    from cc.services import database
    from cc.utils.errors import CCError

    sqls = []
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": sqls.append(sql))
    monkeypatch.setattr(pg, "database_exists", lambda name: False)
    with pytest.raises(CCError):
        database.restore("mydb")
    assert not any("DROP DATABASE" in s for s in sqls)


def test_invalid_db_name_rejected(_db, monkeypatch):
    from cc.services import database
    from cc.utils.errors import CCError

    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": None)
    with pytest.raises(CCError):
        database.copy('evil"; DROP DATABASE "prod')


def test_extend_runs_expiry_sql(_db, monkeypatch):
    from cc.services import database

    seen = {}
    monkeypatch.setattr(pg, "run_sql", lambda sql, db="postgres": seen.update(sql=sql, db=db))
    database.extend("acme")
    assert seen["db"] == "acme"
    assert "database.expiration_date" in seen["sql"]


def test_reconcile_adds_and_populates(_db, monkeypatch):
    _stub_pg(
        monkeypatch,
        names=["alpha", "beta"],
        sizes={"alpha": 100, "beta": 200},
        logins={"alpha": {"last_login": "2026-01-01T00:00:00", "is_odoo": True}},
    )

    result = database.reconcile()
    assert result["added"] == 2

    rows = _rows()
    assert rows["alpha"].in_pg and rows["beta"].in_pg
    assert rows["alpha"].size_bytes == 100
    assert rows["alpha"].is_odoo
    assert rows["alpha"].last_login == "2026-01-01T00:00:00"
    assert not rows["beta"].is_odoo


def test_reconcile_updates_existing_not_duplicate(_db, monkeypatch):
    _stub_pg(monkeypatch, names=["alpha"], sizes={"alpha": 100})
    database.reconcile()
    _stub_pg(monkeypatch, names=["alpha"], sizes={"alpha": 999})
    result = database.reconcile()

    assert result["added"] == 0 and result["updated"] == 1
    rows = _rows()
    assert len(rows) == 1
    assert rows["alpha"].size_bytes == 999


def test_drop_via_docker_flags_cache_keeps_row(_db, monkeypatch):
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import database, environment, project
    from cc.utils.errors import CCError

    proj = project.create("acme")
    environment.create(
        name="staging", project_id=proj["id"], version_name="17.0", version_path="/tmp/v17",
        project_path="/tmp/acme", github_url="", branch_name="main",
        database_name="victim", module_names=[],
    )

    # No direct connection → must fall back to docker exec.
    monkeypatch.setattr(pg, "drop_db", lambda name: (_ for _ in ()).throw(CCError("no direct")))
    seen = {}
    import cc.services.pg_docker as pgd
    monkeypatch.setattr(pgd, "drop_database", lambda name: seen.setdefault("dropped", name))

    database.drop("victim")

    assert seen["dropped"] == "victim"                     # used the docker fallback
    with database_connection_manager():
        row = Database.find_by(name="victim", limit=1)
        assert row is not None and not row.in_pg           # row kept, flagged gone


def test_rename_via_docker_updates_cache(_db, monkeypatch):
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import database, environment, project
    from cc.utils.errors import CCError

    proj = project.create("acme")
    environment.create(
        name="staging", project_id=proj["id"], version_name="17.0", version_path="/tmp/v17",
        project_path="/tmp/acme", github_url="", branch_name="main",
        database_name="old_db", module_names=[],
    )

    monkeypatch.setattr(pg, "rename_db", lambda old, new: (_ for _ in ()).throw(CCError("no direct")))
    seen = {}
    import cc.services.pg_docker as pgd
    monkeypatch.setattr(pgd, "rename_database", lambda old, new: seen.setdefault("r", (old, new)))

    database.rename("old_db", "new_db")

    assert seen["r"] == ("old_db", "new_db")               # docker fallback used
    with database_connection_manager():
        assert Database.find_by(name="new_db", limit=1)
        assert not Database.find_by(name="old_db", limit=1)


def test_reconcile_flags_vanished_keeps_row(_db, monkeypatch):
    _stub_pg(monkeypatch, names=["alpha", "beta"])
    database.reconcile()

    # beta dropped from Postgres
    _stub_pg(monkeypatch, names=["alpha"])
    result = database.reconcile()

    assert result["gone"] == 1
    rows = _rows()
    assert "beta" in rows          # row kept (links/metadata survive)
    assert not rows["beta"].in_pg  # but flagged gone
    assert rows["alpha"].in_pg


# ── helpers.get_all_db_names reads the cache (in_pg) ──────────────────────

def test_get_all_db_names_reads_cache_and_filters(_db):
    from cc.utils.helpers import Helpers
    with database_connection_manager():
        Database.create({"name": "alpha", "in_pg": True})
        Database.create({"name": "beta", "in_pg": False})
        Database.create({"name": "acme-CC-COPY", "in_pg": True})
        Database.create({"name": "postgres", "in_pg": True})
    names = Helpers.get_all_db_names()
    assert "alpha" in names
    assert "beta" not in names           # in_pg False
    assert "acme-CC-COPY" not in names   # banned word (CC-COPY)
    assert "postgres" not in names       # banned db


def test_get_all_db_names_cold_cache_triggers_reconcile(_db, monkeypatch):
    """Empty cache (fresh install / pre-3.8 NULL in_pg) → one reconcile, then re-read."""
    from cc.utils import helpers
    from cc.utils.helpers import Helpers
    monkeypatch.setattr(helpers, "_db_cache_reconciled", False)
    calls = {"n": 0}

    def fake_call(method, **kw):
        calls["n"] += 1
        with database_connection_manager():
            Database.create({"name": "late", "in_pg": True})
    monkeypatch.setattr("cc.daemon.client.call", fake_call)

    names = Helpers.get_all_db_names()
    assert calls["n"] == 1 and "late" in names


def test_get_all_db_names_cold_cache_fallback_runs_once(_db, monkeypatch):
    from cc.utils import helpers
    from cc.utils.helpers import Helpers
    monkeypatch.setattr(helpers, "_db_cache_reconciled", False)
    calls = {"n": 0}
    monkeypatch.setattr("cc.daemon.client.call",
                        lambda *a, **k: calls.__setitem__("n", calls["n"] + 1))
    Helpers.get_all_db_names()   # empty → fallback fires
    Helpers.get_all_db_names()   # still empty, flag set → no second daemon hit
    assert calls["n"] == 1


# ── database.get_relevant_names uses the single active row (3.8) ──────────

def test_get_relevant_names_empty_without_active(_db):
    assert database.get_relevant_names() == []


def test_get_relevant_names_single_active_ignores_multi_flag(_db):
    from cc.base.arm.app_state import AppState
    from cc.base.arm.setting import Setting
    from cc.services import environment, project
    proj = project.create("acme")
    env = environment.create(
        name="staging", project_id=proj["id"], version_name="17.0", version_path="/tmp/v17",
        project_path="/tmp/acme", github_url="", branch_name="main",
        database_name="acme", module_names=[],
    )
    with database_connection_manager():
        # multi_version_mode="true" used to take a dead version_id-NOT-NULL branch → [].
        Setting.create({"name": "multi_version_mode", "value": "true"})
        # environment.create already made the "acme" db row; flag it present in PG.
        Database.find_by(name="acme", limit=1).update({"in_pg": True})
        AppState.create({"environment_id": env["id"]})
    assert "acme" in database.get_relevant_names()
