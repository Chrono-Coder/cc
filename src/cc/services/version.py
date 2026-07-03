"""
Version service — Odoo version record management.
"""
import logging

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError

log = logging.getLogger("CC")


@rpc_method
def create(name: str, path: str, branch: str = None) -> dict:
    """Create a version record and return {"id": int, "name": str}."""
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        vals = {"name": name, "path": path}
        if branch:
            vals["branch"] = branch
        version = Version.create(vals)
        log.debug(f"create: version '{name}' id={version.id}")
        return {"id": version.id, "name": version.name}


@rpc_method
def delete(version_id: int) -> None:
    """Delete a version record."""
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        version = Version.search([("id", "=", version_id)], limit=1)
        if not version:
            raise NotFoundError(f"Version id={version_id} not found")
        version._delete()
        log.debug(f"delete: version id={version_id} removed")


@rpc_method
def upsert(name: str, path: str, branch: str = None) -> dict:
    """Find-or-create a version by name, updating path/branch if it exists."""
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        vals = {"path": path}
        if branch:
            vals["branch"] = branch
        existing = Version.find_by(name=name, limit=1)
        if existing:
            existing.update(vals)
            log.debug(f"upsert: updated version '{name}'")
            return {"id": existing.id, "name": existing.name}
        else:
            version = Version.create({"name": name, **vals})
            log.debug(f"upsert: created version '{name}' id={version.id}")
            return {"id": version.id, "name": version.name}


@rpc_method
def update_port(version_id: int, port: str) -> None:
    """Update the port on a version record."""
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        version = Version.search([("id", "=", version_id)], limit=1)
        if not version:
            raise NotFoundError(f"Version id={version_id} not found")
        version.update({"port": port})
        log.debug(f"update_port: version={version.name} port={port}")


@rpc_method
def update(version_id: int, **fields) -> None:
    """Generic field update for a version record."""
    from cc.base.arm.version import Version
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        version = Version.search([("id", "=", version_id)], limit=1)
        if not version:
            raise NotFoundError(f"Version id={version_id} not found")
        version.update(fields)
        log.debug(f"update: version id={version_id} fields={list(fields)}")
