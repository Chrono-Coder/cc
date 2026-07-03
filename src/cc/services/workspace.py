"""
Workspace service — business logic for workspace-related operations.

Rules:
- Return Python objects only (no JSON, no print)
- Raise exceptions instead of catching and swallowing
- No transport awareness
"""
from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError


@rpc_method
def create(name: str, path: str = "", is_rnd: bool = False, fork_remote: str = "", upstream_remote: str = "", version_id: int = 0) -> dict:
    """Create a workspace and return {"id": int, "name": str}."""
    import logging
    from cc.base.arm.workspace import Workspace
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        vals = {"name": name}
        if path:
            vals["path"] = path
        if is_rnd:
            vals["is_rnd"] = True
        if fork_remote:
            vals["fork_remote"] = fork_remote
        if upstream_remote:
            vals["upstream_remote"] = upstream_remote
        if version_id:
            vals["version_id"] = version_id
        workspace = Workspace.create(vals)
        log.debug(f"create: workspace '{name}' id={workspace.id}")
        return {"id": workspace.id, "name": workspace.name}


@rpc_method
def delete(workspace_id: int) -> None:
    """Delete a workspace. Unlinks all child projects (sets their workspace_id to NULL)."""
    import logging
    from cc.base.arm.workspace import Workspace
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        workspace = Workspace.search([("id", "=", workspace_id)], limit=1)
        if not workspace:
            raise NotFoundError(f"Workspace id={workspace_id} not found")

        for project in workspace.project_ids:
            project.update({"workspace_id": None})

        workspace._delete()
        log.debug(f"delete: workspace id={workspace_id} removed")


@rpc_method
def get_all() -> list:
    """Return all workspaces as list of dicts with id, name, path, is_rnd, version_id."""
    from cc.base.db import database_connection_manager
    from cc.base.arm.workspace import Workspace

    with database_connection_manager():
        workspaces = Workspace.find_by(orderby="name ASC")
        return [
            {
                "id": w.id,
                "name": w.name,
                "path": w.path or "",
                "is_rnd": w.is_rnd or False,
                "fork_remote": w.fork_remote or "",
                "upstream_remote": w.upstream_remote or "",
                "version_id": w.version_id.id if w.version_id else None,
                "version_name": w.version_id.name if w.version_id else None,
            }
            for w in workspaces
        ]


@rpc_method
def update(workspace_id: int, name: str = "", path: str = "", is_rnd: bool = None, fork_remote: str = "", upstream_remote: str = "", version_id: int = 0) -> None:
    """Update workspace fields. Only non-empty/non-zero values are applied."""
    import logging
    from cc.base.arm.workspace import Workspace
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        workspace = Workspace.search([("id", "=", workspace_id)], limit=1)
        if not workspace:
            raise NotFoundError(f"Workspace id={workspace_id} not found")
        vals = {}
        if name:
            vals["name"] = name
        if path:
            vals["path"] = path
        if is_rnd is not None:
            vals["is_rnd"] = is_rnd
        if fork_remote:
            vals["fork_remote"] = fork_remote
        if upstream_remote:
            vals["upstream_remote"] = upstream_remote
        if version_id:
            vals["version_id"] = version_id
        if vals:
            workspace.update(vals)
            log.debug(f"update: workspace id={workspace_id} → {vals}")


@rpc_method
def assign_project(workspace_id: int, project_id: int) -> None:
    """Assign a project to a workspace."""
    import logging
    from cc.base.arm.workspace import Workspace
    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        workspace = Workspace.search([("id", "=", workspace_id)], limit=1)
        if not workspace:
            raise NotFoundError(f"Workspace id={workspace_id} not found")
        project = Project.search([("id", "=", project_id)], limit=1)
        if not project:
            raise NotFoundError(f"Project id={project_id} not found")
        project.update({"workspace_id": workspace_id})
        log.debug(f"assign_project: project id={project_id} → workspace id={workspace_id}")
