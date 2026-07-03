from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Database(BaseEntity):
    """
    Represents the 'databases' table.
    -- Stores database information.
    """

    _name = "database"
    _order = "name ASC"

    name = Property(type=str, unique=True, required=True)
    last_update = Property(type=str, semantic="datetime")
    clone_db_id = Property(relation="database")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")

    # Cached Postgres metadata — maintained by database.reconcile() so readers
    # (web /databases, cc db, completion) never block on psql. NULL on rows that
    # predate the cache until the next reconcile fills them in.
    in_pg = Property(type=bool)              # present in Postgres right now
    size_bytes = Property(type=int)          # pg_database_size
    last_login = Property(type=str, semantic="datetime")  # MAX(res_users_log.create_date)
    is_odoo = Property(type=bool)            # has res_users_log (i.e. an Odoo DB)
    last_synced_at = Property(type=str, semantic="datetime")
