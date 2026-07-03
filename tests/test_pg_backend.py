"""
pg backend seam: run_sql/load_dump/database_exists route to direct psycopg2 or
docker-exec via a cached _backend() probe. No real Postgres or Docker — both
sides are stubbed, so this exercises the routing/caching logic only.
"""
import pytest

from cc.services import pg, pg_connect, pg_docker


class _Conn:
    def close(self):
        pass


def _boom(*a, **k):
    raise Exception("pg down")


@pytest.fixture(autouse=True)
def _fresh_backend():
    pg.reset_backend()
    yield
    pg.reset_backend()


def test_backend_direct_when_psycopg2_connects(monkeypatch):
    monkeypatch.setattr(pg_connect, "connect", lambda db="postgres": _Conn())
    assert pg._backend() == "direct"


def test_backend_docker_when_direct_fails_and_container_present(monkeypatch):
    monkeypatch.setattr(pg_connect, "connect", _boom)
    monkeypatch.setattr(pg_docker, "discover", lambda: {"container": "c", "user": "odoo"})
    assert pg._backend() == "docker"


def test_backend_direct_when_no_direct_and_no_container(monkeypatch):
    monkeypatch.setattr(pg_connect, "connect", _boom)
    monkeypatch.setattr(pg_docker, "discover", lambda: None)
    assert pg._backend() == "direct"


def test_backend_is_cached(monkeypatch):
    calls = {"n": 0}

    def once(db="postgres"):
        calls["n"] += 1
        return _Conn()
    monkeypatch.setattr(pg_connect, "connect", once)
    assert pg._backend() == "direct"
    assert pg._backend() == "direct"
    assert calls["n"] == 1  # probed once, then cached


def test_reset_backend_forces_reprobe(monkeypatch):
    monkeypatch.setattr(pg_connect, "connect", lambda db="postgres": _Conn())
    assert pg._backend() == "direct"
    # Flip the environment: direct now fails, a container appears.
    monkeypatch.setattr(pg_connect, "connect", _boom)
    monkeypatch.setattr(pg_docker, "discover", lambda: {"container": "c", "user": "odoo"})
    assert pg._backend() == "direct"          # still cached
    pg.reset_backend()
    assert pg._backend() == "docker"          # re-probed after reset


def test_pg_connect_reset_also_clears_backend(monkeypatch):
    """pg_connect.reset() must drop pg's backend cache (settings-change path)."""
    monkeypatch.setattr(pg_connect, "connect", lambda db="postgres": _Conn())
    assert pg._backend() == "direct"
    monkeypatch.setattr(pg_connect, "connect", _boom)
    monkeypatch.setattr(pg_docker, "discover", lambda: {"container": "c", "user": "odoo"})
    pg_connect.reset()
    assert pg._backend() == "docker"


def test_run_sql_routes_to_docker(monkeypatch):
    monkeypatch.setattr(pg, "_backend", lambda: "docker")
    seen = {}
    monkeypatch.setattr(pg_docker, "exec_sql", lambda sql, db="postgres": seen.update(sql=sql, db=db))
    pg.run_sql("SELECT 1", db="acme")
    assert seen == {"sql": "SELECT 1", "db": "acme"}


def test_database_exists_direct(monkeypatch):
    monkeypatch.setattr(pg, "_backend", lambda: "direct")

    class _Cur:
        def __init__(self, row):
            self._row = row

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def execute(self, *a):
            pass

        def fetchone(self):
            return self._row

    class _C:
        def __init__(self, row):
            self._row = row

        def cursor(self):
            return _Cur(self._row)

        def close(self):
            pass

    monkeypatch.setattr(pg, "_open", lambda db="postgres": _C((1,)))
    assert pg.database_exists("x") is True
    monkeypatch.setattr(pg, "_open", lambda db="postgres": _C(None))
    assert pg.database_exists("x") is False


def test_database_exists_routes_to_docker(monkeypatch):
    monkeypatch.setattr(pg, "_backend", lambda: "docker")
    monkeypatch.setattr(pg_docker, "db_exists", lambda name: True)
    assert pg.database_exists("x") is True
