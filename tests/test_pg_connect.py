"""
Self-discovering Postgres connector (pg_connect): probe candidate methods, use
the first that works, cache it, and diagnose. psycopg2.connect is stubbed so the
tests never touch a real Postgres.
"""
import psycopg2
import pytest

from cc.services import pg_connect
from cc.utils.errors import CCError


class _FakeConn:
    def close(self):
        pass


@pytest.fixture(autouse=True)
def _reset_and_isolate(monkeypatch):
    # Deterministic candidate list: configured=none, one socket dir.
    pg_connect.reset()
    monkeypatch.setattr(pg_connect, "_configured_dsn", lambda: None)
    monkeypatch.setattr(pg_connect, "_socket_dirs", lambda: ["/tmp"])
    yield
    pg_connect.reset()


def test_connect_picks_first_working_method(monkeypatch):
    def fake_connect(*args, **kwargs):
        if kwargs.get("host") == "/tmp":      # libpq default (no host) fails first
            return _FakeConn()
        raise psycopg2.OperationalError("no socket")
    monkeypatch.setattr(pg_connect.psycopg2, "connect", fake_connect)

    conn = pg_connect.connect("postgres")
    assert isinstance(conn, _FakeConn)
    assert pg_connect.resolved_label() == "socket /tmp"


def test_connect_caches_method(monkeypatch):
    calls = {"n": 0}

    def fake_connect(*args, **kwargs):
        calls["n"] += 1
        return _FakeConn()  # libpq default works immediately
    monkeypatch.setattr(pg_connect.psycopg2, "connect", fake_connect)

    pg_connect.connect()
    assert pg_connect.resolved_label() == "libpq default"
    first = calls["n"]
    pg_connect.connect()  # should reuse resolved, not re-probe from scratch
    assert calls["n"] == first + 1  # exactly one connect, no re-probe


def test_connect_all_fail_raises_ccerror(monkeypatch):
    def boom(*args, **kwargs):
        raise psycopg2.OperationalError("server down")
    monkeypatch.setattr(pg_connect.psycopg2, "connect", boom)

    with pytest.raises(CCError) as ei:
        pg_connect.connect()
    assert "isn't reachable" in str(ei.value)
    assert "pg.connection" in str(ei.value)  # points the user at config


def test_check_reports_each_method(monkeypatch):
    def fake_connect(*args, **kwargs):
        if kwargs.get("host") == "/tmp":
            return _FakeConn()
        raise psycopg2.OperationalError("nope")
    monkeypatch.setattr(pg_connect.psycopg2, "connect", fake_connect)

    by = {r["method"]: r for r in pg_connect.check()}
    assert by["socket /tmp"]["ok"] is True
    assert by["libpq default"]["ok"] is False
    assert by["libpq default"]["error"]
