from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Module(BaseEntity):
    """
    Represents the 'modules' table.
    -- Stores module information.
    """

    _name = "module"

    name = Property(type=str)
    # Per-environment action used by Odoo launch/database initialization:
    # install | upgrade | draft. NULL from older rows is treated as draft.
    state = Property(type=str, default="draft")
    environment_id = Property(relation="environment")
