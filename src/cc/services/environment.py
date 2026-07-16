"""
Environment service — business logic for environment-related operations.

Rules:
- Return Python objects only (no JSON, no print)
- Raise exceptions instead of catching and swallowing
- No transport awareness
"""
import logging
import os
from typing import Optional

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError, ValidationError

log = logging.getLogger("CC")

# Env lifecycle. NULL status (rows predating the column) counts as "active".
ENV_STATUSES = ("active", "merged", "archived")
# An env that isn't "active" still shows in the default picker if it was used
# within this many days — so a just-merged ticket doesn't vanish mid-flow.
_DEFAULT_VISIBLE_DAYS = 14


def _is_recent(last_used_at, days: int = _DEFAULT_VISIBLE_DAYS) -> bool:
    """True if last_used_at (ISO string) is within `days` of now."""
    if not last_used_at:
        return False
    from datetime import datetime, timedelta, timezone
    try:
        dt = datetime.fromisoformat(last_used_at)
    except (ValueError, TypeError):
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt) <= timedelta(days=days)


def _is_default_visible(env) -> bool:
    """Whether an env shows in the default (non --all) picker.

    - active (or NULL): always visible.
    - archived: always hidden — an explicit "put it away", recency doesn't revive it.
    - merged: a soft state with a grace period — visible while pinned or used
      recently, so a just-merged ticket doesn't vanish mid-flow, then drops off.
    """
    status = env.status or "active"
    if status == "active":
        return True
    if status == "archived":
        return False
    # merged (or any other non-active soft state)
    if env.pinned:
        return True
    return _is_recent(env.last_used_at)


def _is_multi_version() -> bool:
    """Multi-active mode (opt-in): one active env per version, resolved by the
    caller's cwd/version. Off by default → single active env."""
    from cc.base.arm.setting import Setting
    from cc.utils.constants import Constants

    s = Setting.find_by(name=Constants.SETTING_MULTI_VERSION, limit=1)
    return bool(s and s.value == "true")


def _resolve_active_env(version_id: int = None):
    """Return the active Environment, or None.

    Single-active (default): one AppState row, the newest is the active env;
    `version_id` is ignored. Multi-active (`SETTING_MULTI_VERSION`): one slot per
    version — resolve the slot for the caller's `version_id` (cwd-resolved by the
    caller), falling back to the most-recently switched slot when it's unset or
    has no slot yet. Pre-3.8 installs collapse to one on the next switch. Call
    inside a DB context.
    """
    from cc.base.arm.app_state import AppState

    if _is_multi_version() and version_id:
        state = AppState.search([("version_id", "=", version_id)], limit=1)
        if state:
            return state.environment_id
    state = AppState.search([], orderby="id DESC", limit=1)
    return state.environment_id if state else None


@rpc_method
def get_active_database(version_id: int = None) -> Optional[str]:
    """Return the active environment's database name, or None."""
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = _resolve_active_env(version_id=version_id)
        log.debug(f"get_active_database: env={env!r}, database_id={getattr(env, 'database_id', 'N/A')!r}")
        return env.database_id.name if env and env.database_id else None


@rpc_method
def get_addons_path(version_id: int = None) -> Optional[str]:
    """Return every addons container used by the active environment."""
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = _resolve_active_env(version_id=version_id)
        if not env:
            return None
        version_path = env.version_id.path
        project_path = env.project_path
        candidates = [
            os.path.join(version_path, "odoo", "addons"),
            os.path.join(version_path, "odoo", "odoo", "addons"),
            os.path.join(version_path, "enterprise"),
            os.path.join(version_path, "design-themes"),
            project_path,
        ]
        # Project-specific shared addons (for example psae-internal) are
        # configured during setup and must be visible to run/create commands,
        # not only to the IDE launch configuration written by cc switch.
        from cc.utils.helpers import Helpers
        internal_dir = Helpers.get_internal_addons_dir()
        if internal_dir and project_path:
            candidates.append(os.path.join(project_path, internal_dir))
        paths = [p for p in candidates if os.path.isdir(p)]
        return ",".join(paths) if paths else None


@rpc_method
def get_status(version_id: int = None, verbose: bool = False) -> "ProjectStatusDTO":
    """
    Return status data for the active project's environments.

    Args:
        version_id: Caller's version context (for multi-version mode).
        verbose:    If False, return only active environments.
                    If True, return all environments for the project.

    Returns:
        {
            "project": str | None,
            "environments": [
                {
                    "id": int,
                    "name": str,
                    "is_active": bool,
                    "project_path": str,
                    "version": str,
                    "github_url": str,
                    "branch_name": str,
                    "database": str | None,
                    "sh_url": str | None,
                    "modules": [str, ...]
                },
                ...
            ]
        }
    """
    from cc.base.db import database_connection_manager
    from cc.base.arm.environment import Environment
    from cc.services.dto import EnvStatusDTO, ProjectStatusDTO

    with database_connection_manager():
        env = _resolve_active_env(version_id=version_id)

        if env and env.project_id:
            project_name = env.project_id.name
            environments = env.project_id.environment_ids
        else:
            project_name = None
            environments = Environment.search([])

        # single active env (3.8): the one resolved above is the only active one
        active_ids = {env.id} if env else set()

        if not verbose:
            environments = environments.filtered(lambda e: e.id in active_ids)

        return ProjectStatusDTO(
            project=project_name,
            environments=[
                EnvStatusDTO(
                    id=e.id,
                    name=e.name,
                    project_name=e.project_id.name if e.project_id else "",
                    is_active=e.id in active_ids,
                    project_path=e.project_path or "",
                    version=e.version_id.name if e.version_id else "N/A",
                    github_url=e.github_url or "",
                    branch_name=e.branch_name or "",
                    database=e.database_id.name if e.database_id else None,
                    sh_url=e.sh_url or None,
                    modules=[m.name for m in e.module_ids] if e.module_ids else [],
                    last_used_at=e.last_used_at or None,
                )
                for e in environments
            ],
        )


@rpc_method
def switch(env_id: int, version_id: int = None) -> "SwitchResultDTO":
    """
    Update AppState to point to the given environment and log the switch.

    This is the single source of truth for all state-changing switch operations.
    The caller (CLI, web, VSCode) resolves env_id locally and passes it here.
    """
    from datetime import datetime, timedelta, timezone

    from cc.base.arm.app_state import AppState
    from cc.base.arm.environment import Environment
    from cc.base.arm.setting import Setting
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager
    from cc.services.dto import SwitchResultDTO
    from cc.utils.constants import Constants

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")

        # Single-active (default): one AppState row, replaced every switch.
        # Multi-active (opt-in): one slot per version — upsert this version's slot,
        # leaving other versions' slots live (so each version stays resumable).
        if _is_multi_version():
            v_id = version_id or (env.version_id.id if env.version_id else None)
            # Clear any legacy single-mode rows (version_id NULL/0) before upserting.
            for record in AppState.search([("version_id", "IS", None)]):
                record._delete()
            for record in AppState.search([("version_id", "=", 0)]):
                record._delete()
            op = "IS" if v_id is None else "="
            existing = AppState.search([("version_id", op, v_id)], limit=1)
            if existing:
                existing.update({"environment_id": env.id})
            else:
                AppState.create({"environment_id": env.id, "version_id": v_id})
        else:
            # one row, replaced; also clears leftover per-version rows.
            for record in AppState.find_by():
                record._delete()
            AppState.create({"environment_id": env.id})

        now = datetime.now(timezone.utc)

        # Auto-tracking (timesheet.mode == "auto", the default): log this switch as
        # an auto span and flag the previous one if it ran over the threshold. In
        # "manual" mode, switches create no timesheet entries — only explicit
        # `cc time start/end` do. (env.last_used_at is navigation state, always set.)
        mode = Setting.find_by(name=Constants.SETTING_TIMESHEET_MODE, limit=1)
        if not (mode and mode.value == "manual"):
            threshold_setting = Setting.find_by(name=Constants.SETTING_TIMESHEET_THRESHOLD, limit=1)
            try:
                threshold_minutes = int(threshold_setting.value) if threshold_setting else 60
            except (ValueError, TypeError):
                threshold_minutes = 60

            last = SwitchLog.find_by(orderby="id DESC", limit=1)
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.switched_at)
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    if (now - last_dt).total_seconds() / 60 > threshold_minutes:
                        last.update({"flagged": True})
                except (ValueError, TypeError):
                    pass

            SwitchLog.create({"environment_id": env.id, "switched_at": now.isoformat(), "flagged": False, "source": "auto"})

        env.update({"last_used_at": now.isoformat()})

        log.debug(f"switch: env={env.name} (id={env.id})")
        result = SwitchResultDTO(
            env_id=env.id,
            env_name=env.name,
            project_name=env.project_id.name if env.project_id else "",
            project_path=env.project_path or "",
            version_id=env.version_id.id if env.version_id else None,
            version_name=env.version_id.name if env.version_id else "N/A",
            version_path=env.version_id.path if env.version_id else "",
            branch_name=env.branch_name or "",
            database=env.database_id.name if env.database_id else None,
        )

    # Best-effort prune (separate transaction — failure won't roll back the switch).
    # Retention is configurable; 0 disables pruning (keep history forever).
    try:
        with database_connection_manager():
            retention = Setting.find_by(name=Constants.SETTING_TIMESHEET_RETENTION_DAYS, limit=1)
            try:
                retention_days = int(retention.value) if retention and retention.value else 90
            except (ValueError, TypeError):
                retention_days = 90
            if retention_days > 0:
                cutoff = (now - timedelta(days=retention_days)).isoformat()
                for entry in SwitchLog.search([("switched_at", "<", cutoff)]):
                    entry._delete()
    except Exception:
        pass

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    # The opportunistic intel reindex now rides on this event (a daemon-side
    # handler) — the switch service no longer knows about intel. project_path
    # lets the handler locate the Repository.
    _publish(EventType.ENV_SWITCHED, {
        "env_id": result.env_id,
        "env_name": result.env_name,
        "project_path": result.project_path,
    })
    _publish(EventType.SWITCH_LOG_NEW)

    return result


def _env_to_detail_dto(env) -> "EnvDetailDTO":
    from cc.services.dto import EnvDetailDTO
    return EnvDetailDTO(
        id=env.id,
        name=env.name,
        project_name=env.project_id.name if env.project_id else "",
        branch_name=env.branch_name or "",
        database=env.database_id.name if env.database_id else None,
        last_used_at=env.last_used_at or None,
        version_id=env.version_id.id if env.version_id else None,
        version_name=env.version_id.name if env.version_id else "N/A",
        status=env.status or "active",
        pinned=bool(env.pinned),
    )


@rpc_method
def find_by_name(name: str) -> "EnvDetailDTO | None":
    """Return a single environment by name, or None. Raises AmbiguousNameError if multiple projects have an env with this name."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        envs = Environment.search([("name", "=", name)])
        if not envs:
            return None
        if len(envs) > 1:
            projects = ", ".join(e.project_id.name for e in envs if e.project_id)
            raise ValidationError(f"Environment name '{name}' exists in multiple projects: {projects}. Use 'project/env' format.")
        return _env_to_detail_dto(envs[0])


@rpc_method
def find_all_by_name(name: str) -> list:
    """Return every environment with this exact name (one per project, possibly
    several). DTOs carry project_name so callers can disambiguate a collision."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        return [_env_to_detail_dto(e) for e in Environment.search([("name", "=", name)])]


@rpc_method
def find_by_project_name(project_name: str, include_all: bool = False) -> list:
    """Return a project's environments as an EnvDetailDTO list.

    By default only "default-visible" envs are returned (active/pinned/recent),
    so a ticket-per-env R&D project doesn't bloat the picker. Pass
    include_all=True (cc switch --all) to get every env including merged/archived.
    """
    from cc.base.arm.environment import Environment
    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        project = Project.find_by(name=project_name, limit=1)
        if not project:
            return []
        envs = Environment.search([("project_id", "=", project.id)])  # Environment._order = name ASC
        if not include_all:
            envs = [e for e in envs if _is_default_visible(e)]
        return [_env_to_detail_dto(e) for e in envs]


@rpc_method
def create_virtual(name: str, project_id: int, version_id: int = 0) -> dict:
    """
    Create a virtual environment — no path, version, or database.
    Used for time-tracking-only projects (presales, internal, maintenance).
    Returns the serialized EnvDetailDTO dict.
    """
    from dataclasses import asdict
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    vals = {
        "name": name,
        "project_id": project_id,
        "project_path": "",
    }
    if version_id:
        vals["version_id"] = version_id

    with database_connection_manager():
        env = Environment.create(vals)
        log.debug(f"create_virtual: environment '{name}' id={env.id}")
        result = asdict(_env_to_detail_dto(env))

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.ENV_CHANGED)
    return result


@rpc_method
def create(
    name: str,
    project_id: int,
    version_name: str,
    version_path: str,
    project_path: str,
    github_url: str,
    branch_name: str,
    database_name: str,
    module_names: list,
) -> dict:
    """
    Create a new environment with find-or-create for version and database.
    Returns the serialized EnvDetailDTO dict.
    """
    from dataclasses import asdict

    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        version = Version.find_by(name=version_name, limit=1)
        if not version:
            version = Version.create({"name": version_name, "path": version_path})
        elif version.path != version_path:
            version.update({"path": version_path})

        db = Database.find_by(name=database_name, limit=1)
        if not db:
            db = Database.create({"name": database_name})

        env = Environment.create({
            "name": name,
            "project_id": project_id,
            "version_id": version.id,
            "project_path": project_path,
            "github_url": github_url,
            "branch_name": branch_name,
            "database_id": db.id,
            "module_ids": [(0, 0, {"name": m}) for m in module_names] if module_names else [],
        })
        log.debug(f"create: environment '{name}' id={env.id}")
        result = asdict(_env_to_detail_dto(env))

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.ENV_CHANGED)
    return result


@rpc_method
def delete(env_id: int) -> None:
    """Delete an environment and cascade: switch_log entries + orphan database record."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")

        # Cascade: remove switch_log entries
        from cc.base.arm.switch_log import SwitchLog
        for entry in SwitchLog.search([("environment_id", "=", env_id)]):
            entry._delete()

        # Intentionally keep the Database record (a Postgres mirror) — dropping a real PG database is a separate, explicit act.

        env._delete()
        log.debug(f"delete: removed environment id={env_id}")

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.ENV_CHANGED)


@rpc_method
def link_database(env_id: int, database_name: str) -> None:
    """Add a database to the environment's pool (database_ids). Find-or-creates the DB record."""
    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        db = Database.find_by(name=database_name, limit=1)
        if not db:
            db = Database.create({"name": database_name})
        env.update({"database_ids": [(4, db.id, 0)]})
        log.debug(f"link_database: env={env.name} db={database_name}")


@rpc_method
def unlink_database(env_id: int, database_name: str) -> None:
    """Remove a database from the environment's pool."""
    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        db = Database.find_by(name=database_name, limit=1)
        if not db:
            raise NotFoundError(f"Database '{database_name}' not found")
        env.update({"database_ids": [(3, db.id, 0)]})
        log.debug(f"unlink_database: env={env.name} db={database_name}")


@rpc_method
def use_database(env_id: int, database_name: str) -> None:
    """Set the active database (database_id) for an environment. Also links it to the pool."""
    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        db = Database.find_by(name=database_name, limit=1)
        if not db:
            db = Database.create({"name": database_name})
        env.update({"database_id": db.id, "database_ids": [(4, db.id, 0)]})
        log.debug(f"use_database: env={env.name} db={database_name}")


_MUTABLE_FIELDS = {
    "name", "database_id", "version_id", "branch_name", "sh_url",
    "notes", "ticket_ids", "github_url", "pinned", "ssh_host", "ssh_user",
    "project_path",
}


def _validate_fields(fields: dict) -> None:
    invalid = set(fields) - _MUTABLE_FIELDS
    if invalid:
        raise ValueError(f"Cannot update fields: {invalid}")


@rpc_method
def toggle_pin(env_id: int) -> bool:
    """
    Atomically toggle the pinned flag on an environment.
    Returns the new pinned value.

    Keyed by id (not name): environment names aren't unique across projects,
    so a name-based toggle would be ambiguous.
    """
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        new_pinned = not bool(env.pinned)
        env.update({"pinned": new_pinned})
        log.debug(f"toggle_pin: env id={env_id} pinned={new_pinned}")
        return new_pinned


@rpc_method
def update(env_id: int, **fields) -> None:
    """Generic field update for an environment record."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    _validate_fields(fields)
    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        env.update(fields)
        log.debug(f"update: env id={env_id} fields={list(fields)}")


@rpc_method
def set_status(env_id: int, status: str) -> dict:
    """Set an environment's lifecycle status: active | merged | archived.

    "merged"/"archived" drop the env out of the default switch picker (unless
    pinned or used in the last fortnight); "active" restores it.
    """
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    if status not in ENV_STATUSES:
        raise ValidationError(
            f"Invalid status '{status}'. Must be one of: {', '.join(ENV_STATUSES)}"
        )
    with database_connection_manager():
        env = Environment.find_by(id=env_id, limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        env.update({"status": status})
        log.debug(f"set_status: env='{env.name}' -> {status}")
        result = {"id": env.id, "name": env.name, "status": status}

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.ENV_CHANGED)
    return result


@rpc_method
def sweep_stale(days: int = None, status: str = None) -> dict:
    """Auto-mark active envs unused for `days` as stale (merged/archived).

    Reads env.auto_stale_days / env.auto_stale_status when args are omitted, so
    the caller can just fire `sweep_stale()` on every switch and let config decide.
    days <= 0 disables (no-op). Only touches currently-active (or NULL) envs that
    aren't pinned and have a last_used_at older than the window. Returns
    {"swept": n, "status": <applied or None>}.
    """
    from cc.base.arm.environment import Environment
    from cc.base.arm.setting import Setting
    from cc.base.db import database_connection_manager
    from cc.utils.constants import Constants

    swept = 0
    applied = None
    with database_connection_manager():
        if days is None:
            s = Setting.find_by(name=Constants.SETTING_ENV_AUTO_STALE_DAYS, limit=1)
            try:
                days = int(s.value) if s and s.value else 0
            except (ValueError, TypeError):
                days = 0
        if not days or days <= 0:
            return {"swept": 0, "status": None}

        if status is None:
            s = Setting.find_by(name=Constants.SETTING_ENV_AUTO_STALE_STATUS, limit=1)
            status = s.value if s and s.value else "archived"
        if status not in ENV_STATUSES or status == "active":
            status = "archived"
        applied = status

        # Only envs with a last_used_at can be measured for staleness.
        for env in Environment.search([("last_used_at", "IS NOT", None)]):
            if (env.status or "active") != "active":
                continue
            if env.pinned:
                continue
            if env.project_id and env.project_id.no_auto_archive:
                continue  # project opted out of auto-archiving
            if _is_recent(env.last_used_at, days):
                continue
            env.update({"status": status})
            swept += 1

    if swept:
        from cc.daemon.event_bus import EventType
        from cc.daemon.event_bus import publish as _publish
        _publish(EventType.ENV_CHANGED)
    log.debug(f"sweep_stale: swept {swept} env(s) to '{applied}' (days={days})")
    return {"swept": swept, "status": applied}


@rpc_method
def update_modules(env_id: int, module_ids: list) -> None:
    """
    Replace the module list on an environment.
    module_ids: list of (0, 0, {"name": str}) commands or plain name strings.
    """
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        env.update({"module_ids": module_ids})
        log.debug(f"update_modules: env={env.name} modules={module_ids}")


@rpc_method
def update_branch(env_id: int, github_url: str, branch_name: str) -> None:
    """Update the github_url and branch_name on an environment record."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.search([("id", "=", env_id)], limit=1)
        if not env:
            raise NotFoundError(f"Environment id={env_id} not found")
        env.update({"github_url": github_url, "branch_name": branch_name})
        log.debug(f"update_branch: env={env.name} branch={branch_name}")


@rpc_method
def get_all_project_modules(version_id: int = None) -> list:
    """Return sorted list of all modules (main + submodules) for the active environment."""
    from cc.base.db import database_connection_manager
    from cc.utils.helpers import Helpers

    with database_connection_manager():
        env = _resolve_active_env(version_id=version_id)
        if not env:
            return []
        modules, submodules = Helpers.get_all_project_modules(env.project_path)
        return sorted(modules) + sorted(submodules)


@rpc_method
def get_recent_envs(limit: int = 5, include_all: bool = False) -> list:
    """Return the most recently used environments, ordered by last_used_at DESC.

    Default-visible filtering is applied unless include_all=True, so archived/
    stale-merged envs don't surface in the no-arg recent picker. We over-fetch
    then filter so the cap still yields up to `limit` visible rows.
    """
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        envs = Environment.search(
            [("last_used_at", "IS NOT", None)],
            orderby="last_used_at DESC",
            limit=None if not include_all else limit,
        )
        if not include_all:
            envs = [e for e in envs if _is_default_visible(e)][:limit]
        return [_env_to_detail_dto(e) for e in envs]


@rpc_method
def get_previous_env() -> dict | None:
    """The env you were on before the current one — powers `cc switch -`.

    Walks the switch log newest-first and returns the first distinct env that
    isn't the current active one (skipping punch-out/NULL rows, repeats of the
    active env, and entries whose env was since deleted). None if there's no
    prior env to go back to.
    """
    from cc.base.arm.app_state import AppState
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        state = AppState.search([], orderby="id DESC", limit=1)
        active_id = state.environment_id.id if state and state.environment_id else None
        for entry in SwitchLog.search([("environment_id", "IS NOT", None)], orderby="id DESC"):
            env = entry.environment_id
            if not env or not env.id:
                continue
            if env.id != active_id:
                return _env_to_detail_dto(env)
        return None


@rpc_method
def get_env_modules(env_id: int) -> list:
    """Return the custom module names linked to a specific environment."""
    from cc.base.arm.environment import Environment
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        env = Environment.find(env_id)
        if not env or not env.id:
            return []
        return sorted(m.name for m in env.module_ids) if env.module_ids else []
