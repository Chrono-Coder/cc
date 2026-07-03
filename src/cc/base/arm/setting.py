from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Setting(BaseEntity):
    _name = "setting"

    name = Property(type=str, unique=True, required=True)
    value = Property(type=str)
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")
