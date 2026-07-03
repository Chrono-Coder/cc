"""Dockerized Postgres access via `docker exec ... psql` — reaches a container
that only exposes 5432 internally, using its local trust auth (no password)."""
import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor

log = logging.getLogger("CC")

_SEP = "\x1f"            # unit separator — safe field delimiter for psql -F
_TIMEOUT = 15


def _run(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT)


def _setting(key):
    try:
        from cc.base.arm.setting import Setting
        from cc.base.db import database_connection_manager
        with database_connection_manager():
            s = Setting.find_by(name=key, limit=1)
            return s.value.strip() if s and s.value and s.value.strip() else None
    except Exception:
        return None


def _docker_available() -> bool:
    try:
        return _run(["docker", "version", "--format", "{{.Server.Version}}"]).returncode == 0
    except Exception:
        return False


def _ps():
    """[(name, image)] for running containers."""
    try:
        r = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Image}}"])
        if r.returncode != 0:
            return []
        return [tuple(line.split("\t", 1)) for line in r.stdout.splitlines() if "\t" in line]
    except Exception:
        return []


def _inspect_env(name) -> dict:
    try:
        r = _run(["docker", "inspect", name, "--format", "{{json .Config.Env}}"])
        if r.returncode != 0:
            return {}
        env = {}
        # docker emits literal `null` (→ None) for a container with no env vars.
        for item in json.loads(r.stdout.strip() or "[]") or []:
            if "=" in item:
                k, v = item.split("=", 1)
                env[k] = v
        return env
    except Exception:
        return {}


def discover():
    """Find a running Postgres container: {container, user} or None (honors the `pg.container` override)."""
    override = _setting("pg.container")
    if override:
        return {"container": override, "user": _inspect_env(override).get("POSTGRES_USER", "postgres")}
    for name, image in _ps():
        env = _inspect_env(name)
        if "postgres" in image.lower() or "POSTGRES_USER" in env or "POSTGRES_DB" in env:
            return {"container": name, "user": env.get("POSTGRES_USER", "postgres")}
    return None


def _psql_rows(container, user, db, sql):
    """Run a query via docker exec and return rows (list of column-lists)."""
    cmd = ["docker", "exec", container, "psql", "-U", user, "-d", db, "-tAq", "-F", _SEP, "-c", sql]
    r = _run(cmd)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "psql failed").strip().splitlines()[0] if r.stderr.strip() else "psql failed")
    return [line.split(_SEP) for line in r.stdout.splitlines() if line != ""]


def _last_logins(container, user, names):
    def _one(name):
        try:
            rows = _psql_rows(container, user, name, "SELECT MAX(create_date) FROM res_users_log")
            val = rows[0][0] if rows and rows[0] and rows[0][0] != "" else None
            return name, {"last_login": val, "is_odoo": True}
        except Exception:
            return name, {"last_login": None, "is_odoo": False}

    if not names:
        return {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(pool.map(_one, names))


def gather_metadata():
    """Cache payload {names, stats, logins} from a docker Postgres (same shape as the psycopg2 path), or None if no container."""
    c = discover()
    if not c:
        return None
    from cc.services.pg import _SYSTEM_DBS

    container, user = c["container"], c["user"]
    excl = ",".join(f"'{d}'" for d in sorted(_SYSTEM_DBS))
    rows = _psql_rows(
        container, user, "postgres",
        f"SELECT datname, pg_database_size(datname) FROM pg_database "
        f"WHERE datname NOT IN ({excl}) ORDER BY datname",
    )
    names, stats = [], {}
    for row in rows:
        name = row[0]
        size = int(row[1]) if len(row) > 1 and row[1].lstrip("-").isdigit() else None
        names.append(name)
        stats[name] = {"size_bytes": size}
    return {"names": names, "stats": stats, "logins": _last_logins(container, user, names)}


def db_exists(name: str) -> bool:
    """Does `name` exist in the discovered container's Postgres? False if no container."""
    c = discover()
    if not c:
        return False
    safe = name.replace("'", "''")
    rows = _psql_rows(c["container"], c["user"], "postgres",
                      f"SELECT 1 FROM pg_database WHERE datname = '{safe}'")
    return bool(rows)


def drop_database(name: str) -> None:
    """Drop a database inside the discovered container via `docker exec dropdb`; raises RuntimeError on failure."""
    c = discover()
    if not c:
        raise RuntimeError("no running postgres container to drop the database in")
    r = _run(["docker", "exec", c["container"], "dropdb", "-U", c["user"], name])
    if r.returncode != 0:
        msg = (r.stderr or "dropdb failed").strip().splitlines()[-1] if r.stderr.strip() else "dropdb failed"
        raise RuntimeError(msg)


def rename_database(old: str, new: str) -> None:
    """Rename a database inside the container via `docker exec psql ALTER DATABASE`."""
    c = discover()
    if not c:
        raise RuntimeError("no running postgres container to rename the database in")
    _psql_rows(c["container"], c["user"], "postgres", f'ALTER DATABASE "{old}" RENAME TO "{new}"')


def exec_sql(sql: str, db: str = "postgres") -> None:
    """Execute a SQL statement in the container via `docker exec psql -c`; raises RuntimeError on failure."""
    c = discover()
    if not c:
        raise RuntimeError("no running postgres container")
    r = _run([
        "docker", "exec", c["container"], "psql", "-U", c["user"],
        "-d", db, "-v", "ON_ERROR_STOP=1", "-c", sql,
    ])
    if r.returncode != 0:
        msg = (r.stderr or "psql failed").strip().splitlines()[-1] if r.stderr.strip() else "psql failed"
        raise RuntimeError(msg)


def load_dump(db: str, dump_path: str) -> None:
    """Stream a SQL dump into the container's psql over stdin via `docker exec -i` (no copy/volume); raises RuntimeError on failure."""
    c = discover()
    if not c:
        raise RuntimeError("no running postgres container")
    with open(dump_path, "rb") as f:
        r = subprocess.run(
            ["docker", "exec", "-i", c["container"], "psql", "-U", c["user"],
             "-d", db, "-v", "ON_ERROR_STOP=1"],
            stdin=f, capture_output=True, timeout=900,
        )
    if r.returncode != 0:
        err = (r.stderr or b"").decode(errors="replace").strip()
        raise RuntimeError(err.splitlines()[-1] if err else "psql load failed")


def check():
    """Diagnostic rows for `cc db check` — does the docker backend connect?"""
    if not _docker_available():
        return []
    c = discover()
    if not c:
        return [{"method": "docker (no postgres container)", "ok": False,
                 "error": "no running postgres container found"}]
    try:
        _psql_rows(c["container"], c["user"], "postgres", "SELECT 1")
        return [{"method": f"docker exec {c['container']} (user={c['user']})", "ok": True, "error": None}]
    except Exception as e:
        return [{"method": f"docker exec {c['container']}", "ok": False,
                 "error": str(e).splitlines()[0]}]
