from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.constraint import UniqueConstraint
from cc.base.arm.common.property import Property


class DevicePath(BaseEntity):
    _name = "device_path"
    _constraints = [UniqueConstraint("device_id", "project_id")]

    device_id = Property(required=True, relation="device")
    project_id = Property(required=True, relation="project")
    local_path = Property(type=str, required=True)
