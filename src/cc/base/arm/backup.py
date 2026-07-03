from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Backup(BaseEntity):
    """
    Records a named pg_dump snapshot for an environment.
    File stored at: ~/.cc-cli/backups/{env_name}/{timestamp}_{name}.dump
    """

    _name = "backup"
    _order = "created_at DESC"

    name = Property(type=str, required=True)
    note = Property(type=str, semantic="text")
    env_name = Property(type=str, required=True)
    db_name = Property(type=str, required=True)
    database_id = Property(relation="database")
    file_path = Property(type=str, required=True, semantic="path")
    size_bytes = Property(type=int)
    created_at = Property(type=str, required=True, semantic="datetime")
    odoo_version = Property(type=str)
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")
