"""Postgres connection discovery — probe candidate methods (libpq default's
socket dir is unreliable across macOS/Linux), cache the first that works."""
import getpass
import glob
import logging
import os

import psycopg2

from cc.utils.errors import CCError

log = logging.getLogger("CC")

# Winning connection spec (sans dbname), cached for the daemon's life.
_resolved: dict | None = None
_resolved_label: str | None = None


def _first_line(exc) -> str:
    return str(exc).strip().splitlines()[0] if str(exc).strip() else exc.__class__.__name__


def _configured_dsn() -> str | None:
    """A user-set libpq DSN (the `pg.connection` setting), if any."""
    try:
        from cc.base.arm.setting import Setting
        from cc.base.db import database_connection_manager
        with database_connection_manager():
            s = Setting.find_by(name="pg.connection", limit=1)
            return s.value.strip() if s and s.value and s.value.strip() else None
    except Exception:
        return None


def _socket_dirs() -> list[str]:
    """Existing dirs that might hold a `.s.PGSQL.*` socket, mac + linux."""
    candidates = [
        "/tmp", "/var/run/postgresql",
        "/opt/homebrew/var/postgres", "/usr/local/var/postgres",
    ]
    candidates += sorted(glob.glob("/opt/homebrew/var/postgresql@*"))
    candidates += sorted(glob.glob("/usr/local/var/postgresql@*"))
    candidates += sorted(glob.glob(os.path.expanduser("~/Library/Application Support/Postgres/var-*")))
    seen, out = set(), []
    for d in candidates:
        if d not in seen and os.path.isdir(d):
            seen.add(d)
            out.append(d)
    return out


def _candidates() -> list[tuple[str, dict]]:
    """(label, spec) connection methods in priority order; spec is a {"_dsn_base"} DSN or psycopg2 connect kwargs."""
    cands: list[tuple[str, dict]] = []
    dsn = _configured_dsn()
    if dsn:
        cands.append(("configured (pg.connection)", {"_dsn_base": dsn}))
    cands.append(("libpq default", {}))
    for d in _socket_dirs():
        cands.append((f"socket {d}", {"host": d}))
    user = getpass.getuser()
    for u in (user, "postgres"):
        cands.append((f"tcp localhost user={u}", {"host": "localhost", "port": 5432, "user": u}))
    return cands


def _do_connect(spec: dict, db_name: str):
    if "_dsn_base" in spec:
        return psycopg2.connect(f"{spec['_dsn_base']} dbname={db_name}")
    return psycopg2.connect(dbname=db_name, **spec)


def connect(db_name: str = "postgres"):
    """Connect, discovering and caching the working method on first use; raises CCError listing every attempt if none work."""
    global _resolved, _resolved_label
    if _resolved is not None:
        return _do_connect(_resolved, db_name)

    attempts = []
    for label, spec in _candidates():
        try:
            conn = _do_connect(spec, db_name)
        except psycopg2.OperationalError as e:
            attempts.append((label, _first_line(e)))
            continue
        _resolved, _resolved_label = spec, label
        log.debug(f"pg: connected via {label}")
        return conn

    tried = "\n".join(f"  • {label}: {err}" for label, err in attempts)
    raise CCError(
        "PostgreSQL isn't reachable. Tried:\n" + tried +
        "\n\nIf PG runs somewhere these don't cover (e.g. Docker with a password), "
        "set a libpq DSN:  cc config  → pg.connection "
        "(e.g. 'host=localhost port=5432 user=postgres password=…')."
    )


def resolved_label() -> str | None:
    """How cc last connected, or None if not yet resolved."""
    return _resolved_label


def reset():
    """Forget the cached method (tests; or after changing pg.connection)."""
    global _resolved, _resolved_label
    _resolved = _resolved_label = None
    from cc.services import pg
    pg.reset_backend()


def check(db_name: str = "postgres") -> list[dict]:
    """Probe every candidate; return [{method, ok, error}] for diagnostics."""
    results = []
    for label, spec in _candidates():
        try:
            conn = _do_connect(spec, db_name)
            conn.close()
            results.append({"method": label, "ok": True, "error": None})
        except Exception as e:
            results.append({"method": label, "ok": False, "error": _first_line(e)})
    return results
