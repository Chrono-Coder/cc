"""
Sync service — device registration and data synchronization.

Handles push/pull of syncable records between devices via the daemon RPC layer.
"""
import logging
import re
import uuid
from datetime import datetime, timezone

from cc.daemon.rpc_method import rpc_method

log = logging.getLogger("CC")

SYNCABLE_TABLES = [
    "version", "setting", "database",
    "project", "environment", "switch_log", "backup",
    # intel tables; _present_syncable() still guards them in case an older DB predates them.
    "repository", "skill_tag", "knowledge_index",
]

# FK columns that reference other syncable tables.
# Maps (table, column) → (referenced_table, natural_key_column).
# "name" = unique name column; "sync_id" = for tables without a global unique name.
_FK_NATURAL_KEYS = {
    ("project", "workspace_id"): ("workspace", "name"),
    ("workspace", "version_id"): ("version", "name"),
    ("environment", "project_id"): ("project", "name"),
    ("environment", "version_id"): ("version", "name"),
    ("environment", "database_id"): ("database", "name"),
    ("switch_log", "environment_id"): ("environment", "sync_id"),
    ("backup", "database_id"): ("database", "name"),
    ("database", "clone_db_id"): ("database", "name"),
    ("skill_tag", "repository_id"): ("repository", "origin_url"),
    ("knowledge_index", "repository_id"): ("repository", "origin_url"),
}

_SECRET_SETTINGS = {"sync.api_key", "sync.server_url", "pg.connection"}
# Credential-shaped setting names (github_pat, *.api_key, *token, ...) never
# sync: they would otherwise land in plaintext on every device and the server.
_SECRET_SETTING_RE = re.compile(r"(key|token|secret|passw|pat)$", re.IGNORECASE)


def _is_secret_setting(name: str) -> bool:
    return name in _SECRET_SETTINGS or bool(_SECRET_SETTING_RE.search(name or ""))


def _present_syncable(conn) -> list:
    """SYNCABLE_TABLES that actually exist — a plugin-owned table (e.g. intel's
    skill_tag) is simply absent when its plugin isn't installed, so it's skipped
    rather than raising 'no such table'."""
    existing = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    return [t for t in SYNCABLE_TABLES if t in existing]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@rpc_method
def register_device(name: str) -> dict:
    """Register a new device and return its API key."""
    from cc.base.arm.device import Device
    from cc.base.db import database_connection_manager

    api_key = str(uuid.uuid4())
    with database_connection_manager():
        existing = Device.find_by(name=name, limit=1)
        if existing:
            return {"id": existing.id, "name": existing.name, "api_key": existing.api_key}
        device = Device.create({"name": name, "api_key": api_key, "created_at": _now_iso()})
        log.info(f"Registered device '{name}'")
        return {"id": device.id, "name": device.name, "api_key": device.api_key}


@rpc_method
def link_project(device_name: str, project_name: str, local_path: str) -> dict:
    """Link a project to a local path on a specific device."""
    from cc.base.arm.device import Device
    from cc.base.arm.device_path import DevicePath
    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        device = Device.find_by(name=device_name, limit=1)
        if not device:
            raise ValueError(f"Device '{device_name}' not found. Run 'cc sync register' first.")
        project = Project.find_by(name=project_name, limit=1)
        if not project:
            raise ValueError(f"Project '{project_name}' not found.")
        existing = DevicePath.find_by(device_id=device.id, project_id=project.id, limit=1)
        if existing:
            existing.update({"local_path": local_path})
            return {"device": device_name, "project": project_name, "local_path": local_path, "updated": True}
        DevicePath.create({"device_id": device.id, "project_id": project.id, "local_path": local_path})
        return {"device": device_name, "project": project_name, "local_path": local_path, "updated": False}


def _enrich_fk_refs(table: str, rows: list[dict], conn) -> list[dict]:
    """Attach _fk_<col> natural key values so the receiving side can resolve FKs."""
    fk_cols = {col: (ref_table, ref_key) for (t, col), (ref_table, ref_key) in _FK_NATURAL_KEYS.items() if t == table}
    if not fk_cols:
        return rows

    enriched = []
    for row in rows:
        row = dict(row)
        for col, (ref_table, ref_key) in fk_cols.items():
            fk_val = row.get(col)
            if fk_val is not None:
                ref_row = conn.execute(
                    f"SELECT {ref_key} FROM {ref_table} WHERE id = ?", (fk_val,)
                ).fetchone()
                row[f"_fk_{col}"] = ref_row[ref_key] if ref_row else None
            else:
                row[f"_fk_{col}"] = None
        enriched.append(row)
    return enriched


@rpc_method
def pull(since: str = None) -> dict:
    """Return all syncable records modified after `since` (ISO timestamp).

    If since is None, returns all records with a sync_id.
    """
    from cc.base.db import database_connection_manager, get_db_connection

    with database_connection_manager():
        conn = get_db_connection()
        result = {}
        for table in _present_syncable(conn):
            if since:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE sync_id IS NOT NULL AND synced_at > ?",
                    (since,),
                ).fetchall()
            else:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE sync_id IS NOT NULL",
                ).fetchall()
            rows = [dict(r) for r in rows]
            if table == "setting":
                rows = [r for r in rows if not _is_secret_setting(r.get("name"))]
            if table == "repository":
                for r in rows:
                    r["path"] = r.get("path") or ""
            result[table] = _enrich_fk_refs(table, rows, conn)
        result["server_time"] = _now_iso()
        return result


def _resolve_fks(table: str, row: dict, conn) -> dict:
    """Replace raw FK integer IDs with local IDs resolved by natural key."""
    fk_cols = {col: (ref_table, ref_key) for (t, col), (ref_table, ref_key) in _FK_NATURAL_KEYS.items() if t == table}
    if not fk_cols:
        return row

    resolved = dict(row)
    for col, (ref_table, ref_key) in fk_cols.items():
        enriched_key = f"_fk_{col}"
        if enriched_key not in resolved:
            continue
        natural_val = resolved.pop(enriched_key)
        if natural_val is None:
            resolved[col] = None
            continue
        local = conn.execute(
            f"SELECT id FROM {ref_table} WHERE {ref_key} = ?", (natural_val,)
        ).fetchone()
        resolved[col] = local["id"] if local else None
    return resolved


@rpc_method
def push(changes: dict) -> dict:
    """Accept syncable records from a client device and upsert them.

    changes: {"environment": [...rows...], "project": [...rows...], ...}
    Returns: {"accepted": int, "skipped": int}
    """
    from cc.base.db import database_connection_manager, get_db_connection

    accepted = 0
    skipped = 0

    with database_connection_manager():
        conn = get_db_connection()
        for table in _present_syncable(conn):
            rows = changes.get(table, [])
            if not rows:
                continue
            # Identifier whitelist: only columns that exist in the local schema
            # are accepted. Row keys come from the remote client, and column
            # names can't be parameterized, so anything else would be
            # attacker-controlled SQL.
            schema_cols = {
                r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            for row in rows:
                sync_id = row.get("sync_id")
                if not sync_id:
                    skipped += 1
                    continue
                # Secret settings never enter via sync either: a hostile or
                # misconfigured peer must not be able to plant credentials
                # that then propagate to every pulling device.
                if table == "setting" and _is_secret_setting(row.get("name")):
                    skipped += 1
                    continue
                existing = conn.execute(
                    f"SELECT id FROM {table} WHERE sync_id = ?", (sync_id,)
                ).fetchone()
                if existing:
                    skipped += 1
                    continue
                row = _resolve_fks(table, row, conn)
                # Stamp ingestion time so this receiver reports the row as synced
                # (not "pending") and so incremental `pull(since=...)` can find it.
                row["synced_at"] = _now_iso()
                columns = [
                    k for k in row.keys()
                    if k != "id" and not k.startswith("_fk_") and k in schema_cols
                ]
                if not columns:
                    skipped += 1
                    continue
                placeholders = ", ".join(["?"] * len(columns))
                col_names = ", ".join(columns)
                values = [row[c] for c in columns]
                try:
                    conn.execute(
                        f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})",
                        values,
                    )
                    accepted += 1
                except Exception as e:
                    log.debug(f"Sync push skip ({table}): {e}")
                    skipped += 1

    return {"accepted": accepted, "skipped": skipped, "server_time": _now_iso()}


@rpc_method
def mark_synced(timestamp: str = None) -> dict:
    """Stamp synced_at on locally-stamped rows that aren't marked yet.

    Called after a successful push: every stamped row we sent is now on the
    server (whether the server accepted it as new or skipped it as already
    present), so it is, by definition, synced. Without this, synced_at stays
    NULL forever and `sync status` reports the entire dataset as "pending".
    """
    from cc.base.db import database_connection_manager, get_db_connection

    ts = timestamp or _now_iso()
    with database_connection_manager():
        conn = get_db_connection()
        total = 0
        for table in _present_syncable(conn):
            cur = conn.execute(
                f"UPDATE {table} SET synced_at = ? WHERE sync_id IS NOT NULL AND synced_at IS NULL",
                (ts,),
            )
            total += cur.rowcount
        return {"marked": total}


@rpc_method
def stamp_sync_ids() -> dict:
    """Assign sync_id to all existing rows that don't have one. Run once per device."""
    from cc.base.db import database_connection_manager, get_db_connection

    with database_connection_manager():
        conn = get_db_connection()
        total = 0
        for table in _present_syncable(conn):
            rows = conn.execute(
                f"SELECT id FROM {table} WHERE sync_id IS NULL"
            ).fetchall()
            for row in rows:
                conn.execute(
                    f"UPDATE {table} SET sync_id = ? WHERE id = ?",
                    (str(uuid.uuid4()), row["id"]),
                )
                total += 1
        return {"stamped": total}


@rpc_method
def status() -> dict:
    """Return sync status — pending count per table, device info."""
    from cc.base.db import database_connection_manager, get_db_connection

    with database_connection_manager():
        conn = get_db_connection()
        pending = {}
        for table in _present_syncable(conn):
            count = conn.execute(
                f"SELECT COUNT(*) as c FROM {table} WHERE sync_id IS NOT NULL AND synced_at IS NULL"
            ).fetchone()["c"]
            pending[table] = count
        return {"pending": pending, "syncable_tables": SYNCABLE_TABLES}
