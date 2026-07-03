"""
Dockerized Postgres backend (B): discover a pg container and gather cache
metadata via `docker exec psql`. The docker CLI is stubbed so tests never shell
out for real.
"""
from cc.services import pg_docker


def test_discover_finds_postgres_container(monkeypatch):
    monkeypatch.setattr(pg_docker, "_setting", lambda k: None)
    monkeypatch.setattr(pg_docker, "_ps", lambda: [("web", "odoo:19"), ("odoo19-db-1", "postgres:16-alpine")])
    monkeypatch.setattr(pg_docker, "_inspect_env", lambda n: {"POSTGRES_USER": "odoo"} if n == "odoo19-db-1" else {})

    c = pg_docker.discover()
    assert c == {"container": "odoo19-db-1", "user": "odoo"}


def test_discover_honors_override_setting(monkeypatch):
    monkeypatch.setattr(pg_docker, "_setting", lambda k: "my-db" if k == "pg.container" else None)
    monkeypatch.setattr(pg_docker, "_inspect_env", lambda n: {"POSTGRES_USER": "bob"})
    assert pg_docker.discover() == {"container": "my-db", "user": "bob"}


def test_discover_none_when_no_pg(monkeypatch):
    monkeypatch.setattr(pg_docker, "_setting", lambda k: None)
    monkeypatch.setattr(pg_docker, "_ps", lambda: [("web", "nginx:latest")])
    monkeypatch.setattr(pg_docker, "_inspect_env", lambda n: {})
    assert pg_docker.discover() is None


def test_gather_metadata_parses_rows(monkeypatch):
    monkeypatch.setattr(pg_docker, "discover", lambda: {"container": "db", "user": "odoo"})

    def fake_rows(container, user, db, sql):
        if "pg_database_size" in sql:
            return [["alpha", "100"], ["beta", "200"]]
        if "res_users_log" in sql:
            if db == "alpha":
                return [["2026-01-01 00:00:00"]]
            raise RuntimeError('relation "res_users_log" does not exist')
        return []
    monkeypatch.setattr(pg_docker, "_psql_rows", fake_rows)

    data = pg_docker.gather_metadata()
    assert data["names"] == ["alpha", "beta"]
    assert data["stats"]["alpha"]["size_bytes"] == 100
    assert data["stats"]["beta"]["size_bytes"] == 200
    assert data["logins"]["alpha"] == {"last_login": "2026-01-01 00:00:00", "is_odoo": True}
    assert data["logins"]["beta"] == {"last_login": None, "is_odoo": False}


def test_gather_metadata_none_without_container(monkeypatch):
    monkeypatch.setattr(pg_docker, "discover", lambda: None)
    assert pg_docker.gather_metadata() is None


def test_check_reports_connect(monkeypatch):
    monkeypatch.setattr(pg_docker, "_docker_available", lambda: True)
    monkeypatch.setattr(pg_docker, "discover", lambda: {"container": "odoo19-db-1", "user": "odoo"})
    monkeypatch.setattr(pg_docker, "_psql_rows", lambda *a: [["1"]])

    res = pg_docker.check()
    assert len(res) == 1 and res[0]["ok"] is True
    assert "odoo19-db-1" in res[0]["method"]
