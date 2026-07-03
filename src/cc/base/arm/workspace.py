from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Workspace(BaseEntity):
    _name = "workspace"
    _order = "name ASC"

    name = Property(type=str, unique=True, required=True)
    path = Property(type=str, semantic="path")
    is_rnd = Property(type=bool, default=False)
    fork_remote = Property(type=str)
    upstream_remote = Property(type=str)
    version_id = Property(relation="version")
    project_ids = Property(one2many="project", inverse_name="workspace_id")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")
