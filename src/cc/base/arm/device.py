from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Device(BaseEntity):
    _name = "device"

    name = Property(type=str, unique=True, required=True)
    api_key = Property(type=str, unique=True, required=True)
    last_seen_at = Property(type=str, semantic="datetime")
    created_at = Property(type=str, semantic="datetime")
