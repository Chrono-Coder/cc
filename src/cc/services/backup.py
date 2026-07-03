"""
Backup service — backup record management.
"""
import logging

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError

log = logging.getLogger("CC")


@rpc_method
def create(
    name: str,
    env_name: str,
    db_name: str,
    file_path: str,
    size_bytes: int,
    created_at: str,
    database_id: int = 0,
    odoo_version: str = None,
    note: str = None,
) -> None:
    """Create a backup metadata record."""
    from cc.base.arm.backup import Backup
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        vals = {
            "name": name,
            "note": note,
            "env_name": env_name,
            "db_name": db_name,
            "file_path": file_path,
            "size_bytes": size_bytes,
            "created_at": created_at,
            "odoo_version": odoo_version,
        }
        if database_id:
            vals["database_id"] = database_id
        Backup.create(vals)
        log.debug(f"create: backup '{name}' for env='{env_name}' db_id={database_id or '?'}")


@rpc_method
def delete(backup_id: int) -> None:
    """Delete a backup metadata record."""
    from cc.base.arm.backup import Backup
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        backup = Backup.search([("id", "=", backup_id)], limit=1)
        if not backup:
            raise NotFoundError(f"Backup id={backup_id} not found")
        backup._delete()
        log.debug(f"delete: backup id={backup_id} removed")
