from cc.base.arm.common.base_entity import BaseEntity
from cc.base.arm.common.property import Property


class Project(BaseEntity):
    _name = "project"
    _order = "name ASC"

    name = Property(type=str, unique=True, required=True)
    is_virtual = Property(type=bool, default=False)
    # When set, this project's envs are exempt from auto-archiving (env.sweep_stale).
    # NULL (existing rows) reads false → swept normally; new projects default false.
    no_auto_archive = Property(type=bool, default=False)
    # R&D only: which shared repo the project's module(s) live in
    # (odoo|enterprise|upgrade). Empty for non-R&D projects. Used by creation
    # (scaffolding, branch-autocomplete scoping); checkout follows the branch
    # across all repos regardless.
    home_repo = Property(type=str)
    # R&D only: the ticket's starting branch (e.g. "19.0-fix-issue"). Anchors
    # forward-port discovery — ports are "<target>-<main_branch>-fw".
    main_branch = Property(type=str)
    workspace_id = Property(relation="workspace")
    environment_ids = Property(one2many="environment", inverse_name="project_id")
    sync_id = Property(type=str)
    synced_at = Property(type=str, semantic="datetime")
