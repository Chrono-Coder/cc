"""
An unreachable Postgres should surface a friendly one-liner, not a raw libpq
traceback. As of the self-discovering connector (pg_connect), the friendly
CCError is raised by the connector after every candidate method fails, and
pg._open() / _connect() propagate it. The resilient per-DB probes keep degrading
to "no data" instead.
"""
import psycopg2
import pytest

from cc.services import pg, pg_connect
from cc.utils.errors import CCError


def test_open_surfaces_friendly_ccerror_when_unreachable(monkeypatch):
    pg_connect.reset()
    monkeypatch.setattr(pg_connect, "_configured_dsn", lambda: None)
    monkeypatch.setattr(pg_connect, "_socket_dirs", lambda: [])

    def _boom(*args, **kwargs):
        raise psycopg2.OperationalError("could not connect to server: Connection refused")
    monkeypatch.setattr(pg_connect.psycopg2, "connect", _boom)

    with pytest.raises(CCError) as exc:
        pg._open()
    assert "isn't reachable" in str(exc.value)
    pg_connect.reset()


def test_open_passes_through_a_live_connection(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(pg, "_connect", lambda db_name="postgres": sentinel)
    assert pg._open() is sentinel
