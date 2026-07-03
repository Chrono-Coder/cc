from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Module(BaseEntity):
    """
    Represents the 'modules' table.
    -- Stores module information.
    """

    _name = "module"

    name = Property(type=str)
    environment_id = Property(relation="environment")
