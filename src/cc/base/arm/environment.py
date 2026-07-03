from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.constraint import UniqueConstraint
from cc.base.arm.common.property import Property


class Environment(BaseEntity):
    """
    Represents the 'environments' table.
    -- Represents a specific environment configuration for a project.
    """

    _name = "environment"
    _order = "name ASC"
    _constraints = [UniqueConstraint("project_id", "name")]

    name = Property(type=str, required=True)
    project_path = Property(type=str, semantic="path")
    github_url = Property(type=str, semantic="url")
    branch_name = Property(type=str)

    # --- Relationships (Foreign Keys) ---
    project_id = Property(required=True, relation="project")
    version_id = Property(relation="version")
    database_id = Property(relation="database")
    database_ids = Property(many2many="database")
    module_ids = Property(one2many="module", inverse_name="environment_id")
    last_used_at = Property(type=str, semantic="datetime")
    sh_url = Property(type=str, semantic="url")
    notes = Property(type=str, semantic="text")
    ticket_ids = Property(type=str, semantic="csv")
    ssh_host = Property(type=str)
    ssh_user = Property(type=str)
    pinned = Property(type=bool)
    # Lifecycle: "active" (default) | "merged" | "archived". Drives the default
    # switch picker, which hides non-active envs unless pinned/recently used —
    # keeps ticket-per-env R&D workspaces from bloating the list. NULL == active
    # (rows created before this column existed).
    status = Property(type=str, default="active")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")

    @property
    def database(self):
        """Resolved database name — duck-type parity with EnvDetailDTO.database."""
        return self.database_id.name if self.database_id else None
