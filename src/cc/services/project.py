"""
Project service — business logic for project-related operations.

Rules:
- Return Python objects only (no JSON, no print)
- Raise exceptions instead of catching and swallowing
- No transport awareness
"""
from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError


@rpc_method
def create(name: str, is_virtual: bool = False, home_repo: str = "", main_branch: str = "") -> dict:
    """Create a project record.

    home_repo (R&D only) records which shared repo the modules live in;
    main_branch (R&D only) is the ticket's starting branch, used to discover
    forward-ports. Returns {"id", "name", "is_virtual", "home_repo", "main_branch"}.
    """
    import logging

    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        vals = {"name": name, "is_virtual": is_virtual}
        if home_repo:
            vals["home_repo"] = home_repo
        if main_branch:
            vals["main_branch"] = main_branch
        project = Project.create(vals)
        log.debug(f"create: project '{name}' id={project.id} virtual={is_virtual} home_repo={home_repo!r} main_branch={main_branch!r}")
        result = {
            "id": project.id,
            "name": project.name,
            "is_virtual": bool(project.is_virtual),
            "home_repo": project.home_repo or "",
            "main_branch": project.main_branch or "",
        }

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.PROJECT_CHANGED)
    return result


@rpc_method
def delete(project_id: int) -> None:
    """Delete a project and cascade: all environments (+ switch_log), then project.

    Database records (a Postgres mirror) are NOT touched — dropping a real PG DB is only ever the explicit cc db drop / database.drop path.
    """
    import logging

    from cc.base.arm.project import Project
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    log = logging.getLogger("CC")
    with database_connection_manager():
        project = Project.search([("id", "=", project_id)], limit=1)
        if not project:
            raise NotFoundError(f"Project id={project_id} not found")

        for env in project.environment_ids:
            for entry in SwitchLog.search([("environment_id", "=", env.id)]):
                entry._delete()
            env._delete()

        project._delete()
        log.debug(f"delete: project id={project_id} removed with all environments")

    from cc.daemon.event_bus import EventType
    from cc.daemon.event_bus import publish as _publish
    _publish(EventType.PROJECT_CHANGED)


@rpc_method
def set_auto_archive(project_id: int, exempt: bool) -> dict:
    """Exempt (or re-include) a project's envs from auto-archiving. Returns
    {"name", "no_auto_archive"}."""
    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        project = Project.search([("id", "=", project_id)], limit=1)
        if not project:
            raise NotFoundError(f"Project id={project_id} not found")
        project.update({"no_auto_archive": bool(exempt)})
        return {"name": project.name, "no_auto_archive": bool(exempt)}


@rpc_method
def get_all() -> list:
    """Return sorted list of all project names."""
    from cc.base.arm.project import Project
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        projects = Project.find_by(orderby="name ASC")
        return [p.name for p in projects]
