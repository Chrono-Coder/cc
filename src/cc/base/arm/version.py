from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Version(BaseEntity):
    _name = "version"
    _order = "name ASC"

    name = Property(type=str, unique=True, required=True)
    path = Property(type=str, required=True, semantic="path")
    port = Property(type=str, default="8069")
    pyenv_virtualenv = Property(type=str)
    branch = Property(type=str)
    last_fetched_at = Property(type=str, semantic="datetime")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")
