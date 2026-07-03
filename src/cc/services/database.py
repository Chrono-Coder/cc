"""
Database service — business logic for database-related operations.

Rules:
- Return Python objects only (no JSON, no print)
- Raise exceptions instead of catching and swallowing
- No transport awareness
"""
import re

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import CCError, NotFoundError

_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _validate_db_name(name: str) -> None:
    """Guard names interpolated into SQL (copy/restore/extend/init) — same rule as pg.drop_db/rename_db."""
    if not name or not _DB_NAME_RE.match(name):
        raise CCError(f"Invalid database name: {name!r}")


@rpc_method
def create(name: str) -> int:
    """Create a database record and return its id."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        db = Database.create({"name": name})
        log.debug(f"create: database '{name}' id={db.id}")
        return db.id


@rpc_method
def delete(database_id: int) -> None:
    """Delete a database record."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        db = Database.search([("id", "=", database_id)], limit=1)
        if not db:
            raise NotFoundError(f"Database id={database_id} not found")
        db._delete()
        log.debug(f"delete: database id={database_id} removed")


@rpc_method
def update(database_id: int, **fields) -> None:
    """Generic field update for a database record."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        db = Database.search([("id", "=", database_id)], limit=1)
        if not db:
            raise NotFoundError(f"Database id={database_id} not found")
        db.update(fields)
        log.debug(f"update: database id={database_id} fields={list(fields)}")


@rpc_method
def link_to_env(env_id: int, db_name: str) -> None:
    """Find or create a database record by name and link it to an environment."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        db = Database.find_by(name=db_name, limit=1)
        if not db:
            db = Database.create({"name": db_name})
        env.update({"database_id": db.id})
        log.debug(f"link_to_env: env id={env_id} → database '{db_name}' id={db.id}")


@rpc_method
def drop(name: str) -> dict:
    """Drop a Postgres database (direct, falling back to docker exec) and flag its cache row in_pg=False (kept, not deleted, to preserve env links). Raises CCError on failure."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import pg, pg_docker
    from cc.utils.errors import CCError

    log = logging.getLogger("CC")

    try:
        pg.drop_db(name)
    except CCError:
        try:
            pg_docker.drop_database(name)
        except Exception as e:
            raise CCError(f"Couldn't drop database '{name}': {e}") from e

    with database_connection_manager():
        db = Database.find_by(name=name, limit=1)
        if db:
            db.update({"in_pg": False})

    log.debug(f"drop: database '{name}' dropped, cache flagged in_pg=False")
    return {"name": name}


@rpc_method
def rename(old: str, new: str) -> dict:
    """Rename a Postgres database (direct, falling back to docker exec) and update the cache row's name. Raises CCError on failure."""
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import pg, pg_docker
    from cc.utils.errors import CCError

    log = logging.getLogger("CC")
    try:
        pg.rename_db(old, new)
    except CCError:
        try:
            pg_docker.rename_database(old, new)
        except Exception as e:
            raise CCError(f"Couldn't rename '{old}' → '{new}': {e}") from e

    with database_connection_manager():
        db = Database.find_by(name=old, limit=1)
        if db:
            db.update({"name": new})

    log.debug(f"rename: database '{old}' → '{new}'")
    return {"old": old, "new": new}


_COPY_SUFFIX = "-CC-COPY"

# Odoo demo/expiry hack: push the expiration date out and disable the update cron.
_EXTEND_SQL = """\
UPDATE ir_config_parameter SET value = '2099-12-31 23:59:59' WHERE key = 'database.expiration_date';
INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
SELECT 'database.expiration_date', '2099-12-31 23:59:59', 1, 1, now(), now()
WHERE NOT EXISTS (SELECT 1 FROM ir_config_parameter WHERE key = 'database.expiration_date');
UPDATE ir_cron SET active = false WHERE id IN (
    SELECT res_id FROM ir_model_data WHERE module = 'mail' AND name = 'ir_cron_update_notify'
);"""


def _drop_db_routed(name: str) -> None:
    """Terminate active sessions, then DROP DATABASE IF EXISTS — backend-routed
    (works against dockerized PG too). The destructive ops (copy/restore/init)
    use this so a live session can't block the drop with "database is being
    accessed by other users". Mirrors the terminate-then-drop in pg.drop_db.
    """
    from cc.services import pg

    _validate_db_name(name)
    pg.run_sql(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
        f" WHERE datname = '{name}' AND pid <> pg_backend_pid()"
    )
    pg.run_sql(f'DROP DATABASE IF EXISTS "{name}"')


@rpc_method
def copy(src: str) -> dict:
    """Copy `src` → `src-CC-COPY` via CREATE DATABASE … TEMPLATE (backend-routed); drops a stale copy first. Returns {src, dest}."""
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import pg

    _validate_db_name(src)
    dest = f"{src}{_COPY_SUFFIX}"
    _drop_db_routed(dest)
    pg.run_sql(f'CREATE DATABASE "{dest}" WITH TEMPLATE "{src}"')
    with database_connection_manager():
        if not Database.find_by(name=dest, limit=1):
            Database.create({"name": dest, "in_pg": True})
    return {"src": src, "dest": dest}


@rpc_method
def restore(src: str) -> dict:
    """Restore `src` from its `src-CC-COPY` template (backend-routed; copy must exist). Returns {src, template}."""
    from cc.services import pg

    _validate_db_name(src)
    template = f"{src}{_COPY_SUFFIX}"
    # Verify the template exists in LIVE Postgres before dropping the target — a
    # stale cache must never let us drop a database we then can't recreate.
    if not pg.database_exists(template):
        raise CCError(f"Template database '{template}' not found in Postgres — run `cc db copy {src}` first.")
    _drop_db_routed(src)
    pg.run_sql(f'CREATE DATABASE "{src}" WITH TEMPLATE "{template}"')
    return {"src": src, "template": template}


@rpc_method
def extend(db: str) -> None:
    """Push the Odoo expiry date to 2099 and disable the update cron on `db` (backend-routed)."""
    from cc.services import pg

    _validate_db_name(db)
    pg.run_sql(_EXTEND_SQL, db=db)


@rpc_method
def init_from_dump(name: str, dump_path: str, clean_path: str = None) -> dict:
    """Drop+recreate `name` and load a SQL dump (backend-routed), optionally a cleanup script after; ensures the cache record."""
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    from cc.services import pg

    _validate_db_name(name)
    _drop_db_routed(name)
    pg.run_sql(f'CREATE DATABASE "{name}"')
    pg.load_dump(name, dump_path)
    if clean_path:
        pg.load_dump(name, clean_path)
    with database_connection_manager():
        if not Database.find_by(name=name, limit=1):
            Database.create({"name": name, "in_pg": True})
    return {"name": name}


@rpc_method
def reconcile() -> dict:
    """Sync the Database cache with live Postgres — upsert live DBs (in_pg=True), flag missing ones in_pg=False (kept, not deleted). Returns {added, updated, gone}."""
    import datetime
    import logging

    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    names, stats, logins = _gather_pg_metadata()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    pg_set = set(names)

    added = updated = gone = 0
    with database_connection_manager():
        existing = {d.name: d for d in Database.find_by()}
        for name in names:
            login = logins.get(name) or {}
            vals = {
                "in_pg": True,
                "size_bytes": (stats.get(name) or {}).get("size_bytes"),
                "last_login": login.get("last_login"),
                "is_odoo": login.get("is_odoo", False),
                "last_synced_at": now,
            }
            row = existing.get(name)
            if row:
                row.update(vals)
                updated += 1
            else:
                Database.create({"name": name, **vals})
                added += 1
        for name, row in existing.items():
            if name not in pg_set and row.in_pg:
                row.update({"in_pg": False, "last_synced_at": now})
                gone += 1

    log.debug(f"reconcile: +{added} ~{updated} -{gone} (pg={len(pg_set)})")
    return {"added": added, "updated": updated, "gone": gone}


def _gather_pg_metadata():
    """Pull (names, stats, logins) from Postgres — direct connection, falling back to docker exec; same shape from either backend."""
    import logging

    from cc.services import pg, pg_docker
    from cc.utils.errors import CCError

    log = logging.getLogger("CC")
    try:
        names = pg.list_databases()
        stats = {s["datname"]: s for s in pg.get_db_stats()}
        logins = pg.get_last_logins(names) if names else {}
        return names, stats, logins
    except CCError:
        data = pg_docker.gather_metadata()
        if data is None:
            raise  # no direct connection and no docker container
        log.debug("reconcile: using docker-exec backend")
        return data["names"], data["stats"], data["logins"]


@rpc_method
def get_relevant_names() -> list:
    """Return database names relevant to the active project."""
    from cc.base.arm.app_state import AppState
    from cc.base.db import database_connection_manager
    from cc.utils.helpers import Helpers

    with database_connection_manager():
        state = AppState.search([], orderby="id DESC", limit=1)
        if not state or not state.environment_id:
            return []
        project_name = state.environment_id.project_id.name
        return Helpers.get_relevant_project_db_names(project_name)
