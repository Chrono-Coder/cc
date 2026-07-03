"""
Postgres service — runs queries against Odoo databases via psycopg2.

Rules:
- Return Python objects only (no JSON, no print)
- Raise exceptions instead of catching and swallowing
- No transport awareness
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError

log = logging.getLogger("CC")

_SYSTEM_DBS = {"postgres", "template0", "template1", "odoo"}

# ---------------------------------------------------------------------------
# TTL cache — daemon is long-lived, so cache expensive PG results in memory.
# ---------------------------------------------------------------------------
_cache: dict[str, tuple[float, object]] = {}  # key → (expires_at, value)


def _cached(key: str, ttl: int, fn):
    """Return cached value if fresh, otherwise call fn(), cache, and return."""
    now = time.monotonic()
    entry = _cache.get(key)
    if entry and entry[0] > now:
        return entry[1]
    value = fn()
    _cache[key] = (now + ttl, value)
    return value


def _connect(db_name: str = "postgres"):
    """Open a connection via the self-discovering connector (pg_connect)."""
    from cc.services import pg_connect
    return pg_connect.connect(db_name)


def _open(db_name: str = "postgres"):
    """User-facing connect — pg_connect raises a friendly CCError if nothing connects."""
    return _connect(db_name)


_backend_cache = None


def _backend() -> str:
    """Which backend SQL writes use: "direct" (psycopg2) or "docker" (exec psql), probed once and cached."""
    global _backend_cache
    if _backend_cache:
        return _backend_cache
    from cc.services import pg_connect, pg_docker
    try:
        pg_connect.connect("postgres").close()
        _backend_cache = "direct"
    except Exception:
        _backend_cache = "docker" if pg_docker.discover() else "direct"
    return _backend_cache


def reset_backend() -> None:
    """Forget the cached backend choice — call after pg.connection/pg.container changes or PG comes up."""
    global _backend_cache
    _backend_cache = None
    _cache.clear()


@rpc_method
def database_exists(name: str) -> bool:
    """Does `name` exist in live Postgres? Backend-routed (direct or docker exec)."""
    if _backend() == "docker":
        from cc.services import pg_docker
        return pg_docker.db_exists(name)
    conn = _open()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
            return cur.fetchone() is not None
    finally:
        conn.close()


@rpc_method
def run_sql(sql: str, db: str = "postgres") -> None:
    """Execute a SQL statement against `db` via the active backend (autocommit; for DDL/one-off DML)."""
    if _backend() == "docker":
        from cc.services import pg_docker
        pg_docker.exec_sql(sql, db)
        return
    conn = _open(db)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
    finally:
        conn.close()


@rpc_method
def backend() -> str:
    """Active SQL backend: "direct" or "docker" (callers adapt host-specific steps like the filestore copy)."""
    return _backend()


@rpc_method
def load_dump(db: str, dump_path: str) -> None:
    """Load a SQL dump file into `db` via the active backend."""
    if _backend() == "docker":
        from cc.services import pg_docker
        pg_docker.load_dump(db, dump_path)
        return
    import subprocess
    with open(dump_path) as f:
        r = subprocess.run(["psql", "-d", db], stdin=f, capture_output=True, text=True)
    if r.returncode != 0:
        from cc.utils.errors import CCError
        raise CCError(f"psql restore failed: {r.stderr.strip()}")


@rpc_method
def check() -> list:
    """Diagnostic: probe every candidate connection method (incl. docker-exec) and report results. Powers `cc db check`."""
    from cc.services import pg_connect, pg_docker
    return pg_connect.check() + pg_docker.check()


@rpc_method
def list_databases() -> list:
    """Return all user database names, excluding system databases."""
    def _fetch():
        with _open() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT datname FROM pg_database WHERE datname != ALL(%s) ORDER BY datname",
                    (_list(_SYSTEM_DBS),),
                )
                return [row[0] for row in cur.fetchall()]
    return _cached("list_databases", 60, _fetch)


@rpc_method
def get_db_stats() -> list:
    """Return per-DB stats: datname, txns, stats_reset, size_bytes."""
    def _fetch():
        with _open() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        s.datname,
                        s.xact_commit + s.xact_rollback,
                        s.stats_reset::text,
                        pg_database_size(s.datname)
                    FROM pg_stat_database s
                    WHERE s.datname != ALL(%s)
                    ORDER BY s.datname
                    """,
                    (_list(_SYSTEM_DBS),),
                )
                return [
                    {
                        "datname": row[0],
                        "txns": row[1],
                        "stats_reset": row[2],
                        "size_bytes": row[3],
                    }
                    for row in cur.fetchall()
                ]
    return _cached("get_db_stats", 60, _fetch)


@rpc_method
def get_last_login(db_name: str) -> object:
    """Return MAX(create_date) from res_users_log for a single DB, or None."""
    try:
        with _connect(db_name) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(create_date) FROM res_users_log")
                row = cur.fetchone()
                val = row[0] if row else None
                return str(val) if val is not None else None
    except Exception:
        return None


@rpc_method
def get_last_logins(db_names: list) -> dict:
    """
    Batch: return {db_name: {"last_login": str | None, "is_odoo": bool}}.

    is_odoo is True when res_users_log exists (query succeeded).
    is_odoo is False when the table is missing or the DB is unreachable.

    Connections run in parallel via ThreadPoolExecutor (63 serial connections
    → ~300ms; parallel → ~30ms). Results cached for 60s.
    """
    # Cache key includes the sorted DB list so it invalidates when DBs change
    cache_key = "last_logins:" + ",".join(sorted(db_names))

    def _fetch():
        def _query_one(name):
            try:
                with _connect(name) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT MAX(create_date) FROM res_users_log")
                        row = cur.fetchone()
                        val = row[0] if row else None
                        return name, {
                            "last_login": str(val) if val is not None else None,
                            "is_odoo": True,
                        }
            except Exception:
                return name, {"last_login": None, "is_odoo": False}

        with ThreadPoolExecutor(max_workers=16) as pool:
            return dict(pool.map(_query_one, db_names))

    return _cached(cache_key, 60, _fetch)


@rpc_method
def rename_db(old_name: str, new_name: str) -> None:
    """Rename a PostgreSQL database (terminates active connections first)."""
    import re
    for name in (old_name, new_name):
        if not re.match(r'^[A-Za-z0-9_.\-]+$', name):
            raise ValueError(f"Invalid database name: {name}")
    conn = _open()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE datname = %s AND pid <> pg_backend_pid()",
                (old_name,),
            )
            cur.execute(f'ALTER DATABASE "{old_name}" RENAME TO "{new_name}"')
    finally:
        conn.close()
    _cache.clear()


@rpc_method
def drop_db(name: str) -> object:
    """DROP DATABASE — terminates active connections first, then drops."""
    import re
    if not re.match(r'^[A-Za-z0-9_.\-]+$', name):
        raise ValueError(f"Invalid database name: {name}")
    conn = _open()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                " WHERE datname = %s AND pid <> pg_backend_pid()",
                (name,),
            )
            try:
                cur.execute(f'DROP DATABASE "{name}"')
            except psycopg2.errors.InvalidCatalogName as e:
                raise NotFoundError(f"Database '{name}' does not exist") from e
    finally:
        conn.close()
    # Invalidate cached DB lists so next call reflects the drop
    _cache.clear()
    return None


def _list(s):
    """Convert a set/iterable to a list (for psycopg2 array params)."""
    return list(s)
