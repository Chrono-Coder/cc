"""
Schema migration runner.

Rules for adding migrations:
  1. Never delete or reorder existing entries — version is the permanent key.
  2. Never mutate an already-committed entry.
  3. Add new entries at the bottom with the next sequential version number.
"""
import logging
import sqlite3
from typing import NamedTuple

from cc.base.db import get_db_connection

log = logging.getLogger("CC")


class Migration(NamedTuple):
    version: int
    description: str
    sql: str


MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        description="Add unique index on environment(project_id, name)",
        sql=(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_environment_project_id_name"
            " ON environment (project_id, name)"
        ),
    ),
    Migration(
        version=2,
        description="Add index on environment(name) for lookup by name",
        sql="CREATE INDEX IF NOT EXISTS idx_environment_name ON environment (name)",
    ),
    Migration(
        version=3,
        description="Add index on switch_log(switched_at) for range queries",
        sql="CREATE INDEX IF NOT EXISTS idx_switch_log_switched_at ON switch_log (switched_at)",
    ),
    Migration(
        version=4,
        description="Add index on switch_log(environment_id) for joins",
        sql="CREATE INDEX IF NOT EXISTS idx_switch_log_environment_id ON switch_log (environment_id)",
    ),
    Migration(
        version=5,
        description="Add index on module(environment_id) for env detail lookups",
        sql="CREATE INDEX IF NOT EXISTS idx_module_environment_id ON module (environment_id)",
    ),
    Migration(
        version=6,
        description="Backfill workspaces from versions (one workspace per version with environments)",
        sql=(
            "INSERT OR IGNORE INTO workspace (name, path, is_rnd, version_id)"
            " SELECT v.name, v.path, 0, v.id"
            " FROM version v"
            " WHERE EXISTS (SELECT 1 FROM environment e WHERE e.version_id = v.id)"
        ),
    ),
    Migration(
        version=7,
        description="Backfill project.workspace_id from first environment's version",
        sql=(
            "UPDATE project SET workspace_id = ("
            "  SELECT w.id FROM workspace w"
            "  INNER JOIN environment e ON e.version_id = w.version_id AND e.project_id = project.id"
            "  LIMIT 1"
            ") WHERE workspace_id IS NULL"
        ),
    ),
    Migration(
        version=8,
        description="Backfill backup.database_id from db_name string",
        sql=(
            "UPDATE backup SET database_id = ("
            "  SELECT id FROM database WHERE name = backup.db_name LIMIT 1"
            ") WHERE database_id IS NULL"
        ),
    ),
    Migration(
        version=9,
        description="Backfill database_environment_rel from environment.database_id",
        sql=(
            "INSERT OR IGNORE INTO database_environment_rel (database_id, environment_id)"
            " SELECT database_id, id FROM environment WHERE database_id IS NOT NULL"
        ),
    ),
    # ---- intel ---------------------------------------------------------
    Migration(
        version=10,
        description="Add index on skill_tag(repository_id, tag) for skill aggregations",
        sql="CREATE INDEX IF NOT EXISTS idx_skill_tag_repo_tag ON skill_tag (repository_id, tag)",
    ),
    Migration(
        version=11,
        description="Add index on skill_tag(committed_at) for time-window queries",
        sql="CREATE INDEX IF NOT EXISTS idx_skill_tag_committed ON skill_tag (committed_at)",
    ),
    Migration(
        version=12,
        description="Add index on skill_tag(commit_sha) for incremental dedup",
        sql="CREATE INDEX IF NOT EXISTS idx_skill_tag_sha ON skill_tag (commit_sha)",
    ),
    Migration(
        version=13,
        description="Add index on knowledge_index(symbol) for who-knows lookups",
        sql="CREATE INDEX IF NOT EXISTS idx_knowledge_symbol ON knowledge_index (symbol)",
    ),
    Migration(
        version=14,
        description="Add index on knowledge_index(repository_id, symbol) for per-repo lookups",
        sql="CREATE INDEX IF NOT EXISTS idx_knowledge_repo_symbol ON knowledge_index (repository_id, symbol)",
    ),
    Migration(
        version=15,
        description="Add unique index on repository(path)",
        sql="CREATE UNIQUE INDEX IF NOT EXISTS uq_repository_path ON repository (path)",
    ),
    Migration(
        version=16,
        description="Create device table",
        sql=(
            "CREATE TABLE IF NOT EXISTS device ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT NOT NULL UNIQUE, "
            "api_key TEXT NOT NULL UNIQUE, "
            "last_seen_at TEXT, "
            "created_at TEXT DEFAULT (datetime('now')))"
        ),
    ),
    Migration(
        version=17,
        description="Create device_path table",
        sql=(
            "CREATE TABLE IF NOT EXISTS device_path ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "device_id INTEGER NOT NULL REFERENCES device(id) ON DELETE CASCADE, "
            "project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE, "
            "local_path TEXT NOT NULL, "
            "UNIQUE(device_id, project_id))"
        ),
    ),
    Migration(
        version=18,
        description="Remove deprecated github_pat and github_username settings (replaced by gh CLI auth)",
        sql="DELETE FROM setting WHERE name IN ('github_pat', 'github_username')",
    ),
]


def run_migrations() -> None:
    """
    Apply any unapplied migrations in version order.

    Must be called from within an active database_connection_manager() context,
    after sync_schema() has already run for all entities.

    Raises on migration failure — never silently swallows schema errors.
    """
    conn = get_db_connection()
    _ensure_migrations_table(conn)

    applied = _get_applied_versions(conn)
    pending = [m for m in MIGRATIONS if m.version not in applied]

    if not pending:
        log.debug("Migrations: nothing to apply.")
        return

    for migration in sorted(pending, key=lambda m: m.version):
        log.info(f"Migrations: applying v{migration.version} — {migration.description}")
        try:
            conn.execute(migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, description, applied_at)"
                " VALUES (?, ?, datetime('now'))",
                (migration.version, migration.description),
            )
        except sqlite3.OperationalError as exc:
            # Defensive: an index/backfill migration whose table doesn't exist yet
            # (sync_schema runs first, so all current models' tables exist — this
            # only fires for a table a migration references before it's created).
            # Skip without marking applied so it runs once the table appears.
            if "no such table" in str(exc).lower():
                log.debug(f"Migrations: v{migration.version} skipped — table absent: {exc}")
                continue
            raise RuntimeError(
                f"Migration v{migration.version} ('{migration.description}') failed: {exc}"
            ) from exc
        except sqlite3.Error as exc:
            raise RuntimeError(
                f"Migration v{migration.version} ('{migration.description}') failed: {exc}"
            ) from exc
        log.info(f"Migrations: v{migration.version} applied.")


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            version     INTEGER NOT NULL UNIQUE,
            description TEXT,
            applied_at  TEXT NOT NULL
        )
        """
    )


def _get_applied_versions(conn: sqlite3.Connection) -> set[int]:
    cursor = conn.execute("SELECT version FROM schema_migrations")
    return {row[0] for row in cursor.fetchall()}
