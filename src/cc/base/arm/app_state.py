from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class AppState(BaseEntity):
    """
    Tracks the single active environment (3.8+): exactly one row, replaced on
    every switch. Active project is derived via environment_id.project_id.

    `version_id` is vestigial — pre-3.8 kept one slot per version (multi-active);
    that was dropped, and new rows leave it NULL. Kept (unused) to avoid a table
    rebuild; resolution is now "the one row," version-independent.
    """

    _name = "app_state"

    environment_id = Property(relation="environment", required=True)
    version_id = Property(relation="version")  # vestigial; see class docstring
