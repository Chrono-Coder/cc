import logging
from dataclasses import dataclass
from typing import Dict, Optional

from cc.base.arm import Environment, Project, Workspace
from cc.daemon.client import call

# Assuming branch_command is one level up in commands/
from ..git.branch_command import BranchCommand

log = logging.getLogger("CC")

# Old verbs kept working as silent aliases (not advertised / not completed).
_PROJECT_ALIASES = {"add": "create", "remove": "delete"}


@dataclass
class EnvironmentConfig:
    name: str
    project: Project
    project_path: str
    version_name: str
    version_path: str
    database_name: str
    github_url: str
    branch_name: str
    module_ids: Optional[list] = None


class ProjectCommand(BranchCommand):
    # No `name` → not a registered command. This is the shared base for the
    # project CRUD verbs (project_crud_command.py) AND for env/open/switch/stat,
    # which all reuse its helpers. The CRUD verbs are `cc project create|list|delete`.
    description = "Create, delete, and manage projects (create, delete, list)."

    def arguments(self):
        return [
            # No argparse choices= so old verbs (add/remove) still work as silent
            # aliases; the completer offers only the canonical verbs.
            self.Argument(
                names=["action"],
                nargs="?",
                default="list",
                complete=("create", "list", "delete"),
                help="Action to perform: create, delete, or list.",
            ),
            self.Argument(
                names=["name"],
                nargs="?",
                help="Project name.",
                complete=Project,
            ),
            self.Argument(
                names=["-y", "--yes"],
                action="store_true",
                help="Skip confirmation prompt.",
            ),
            self.Argument(
                names=["--virtual"],
                action="store_true",
                help="Create a virtual project (no local path, time tracking only).",
            ),
            self.Argument(
                names=["-w", "--workspace"],
                type=str,
                default=None,
                help="Create project in a workspace: cc project create NAME -w WORKSPACE",
            ),
        ]

    def execute(self):
        action = _PROJECT_ALIASES.get(self.args.action, self.args.action)
        project_name = self.args.name

        if action == "create":
            return self._execute_project_add(project_name)
        elif action == "delete":
            return self._execute_project_remove(project_name)
        elif action == "list":
            return self._execute_list()

        self.parser.print_help()
        return False

    def _execute_list(self):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table

        projects = self.project.search([])
        console = get_console()
        if not projects:
            console.print("[warning]No projects found.[/]")
            return True

        active_project_ids = {
            s.environment_id.project_id.id
            for s in self.app_state.find_by()
            if s.environment_id and s.environment_id.project_id
        }

        table = themed_table(title="Projects")
        table.add_column("Name", style="bold")
        table.add_column("Status", style="success")
        for p in projects:
            status = "Active" if p.id in active_project_ids else ""
            table.add_row(p.name, status)
        console.print()
        console.print(table)
        console.print()
        return True

    def _list(self, environments):
        from cc.utils.console import get_console
        from cc.utils.panels import env_card

        console = get_console()
        if not environments:
            console.print("[warning]⚠ No environments found for this project.[/]")
            return

        active_env_ids = {s.environment_id.id for s in self.app_state.find_by()}
        for env in environments:
            is_virtual = bool(env.project_id and env.project_id.is_virtual)
            console.print(env_card({
                "name": env.name,
                "project_name": env.project_id.name if env.project_id else None,
                "project_path": env.project_path,
                "version": env.version_id.name if env.version_id else None,
                "github_url": env.github_url,
                "branch_name": env.branch_name,
                "database": env.database_id.name if env.database_id else None,
                "sh_url": env.sh_url,
                "modules": [m.name for m in env.module_ids] if env.module_ids else [],
                "is_active": env.id in active_env_ids,
                "is_virtual": is_virtual,
                "lifecycle": env.status or "active",
            }))

    def _execute_project_add(self, project_name):
        if not project_name:
            project_name = self.prompter.prompt_input_single("Enter project name to add")

        if not project_name:
            log.error("Project name is required.")
            return False

        is_virtual = self.args.virtual

        if is_virtual:
            result = call("project.create", name=project_name, is_virtual=True)
            if not result:
                log.error(f"Failed to create virtual project '{project_name}'.")
                return False

            workspace_name = self.args.workspace
            version_id = 0
            if workspace_name:
                workspace = Workspace.find_by(name=workspace_name, limit=1)
                if workspace and workspace.version_id:
                    version_id = workspace.version_id.id
                    call("workspace.assign_project", workspace_id=workspace.id, project_id=result["id"])

            call("env.create_virtual", name=project_name, project_id=result["id"], version_id=version_id)
            from cc.utils.console import get_console
            get_console().print(f"[success]✓ Virtual project '{project_name}' created.[/] Use [primary]cc switch {project_name}[/] to start tracking time.")
            return True

        workspace_name = self.args.workspace
        if not workspace_name:
            # Auto-detect an R&D workspace from the current directory so you don't
            # have to pass -w when you're already standing in one.
            detected = self.Helpers.detect_workspace_for_cwd()
            if detected and detected.is_rnd:
                workspace_name = detected.name
                from cc.utils.console import get_console
                get_console().print(
                    f"[muted]Detected R&D workspace '[primary]{workspace_name}[/]' from current directory.[/]"
                )
        if workspace_name:
            return self._execute_add_in_workspace(project_name, workspace_name)

        log.debug(f"Attempting to add/create project: {project_name}")
        project = self._create_project(project_name)
        if not project:
            return False  # _create_project logs errors

        # Calls the complex add logic defined below
        return self._execute_add(project)

    def _execute_add_in_workspace(self, project_name, workspace_name):
        """Create a project in a workspace. R&D workspaces discover the ticket's
        forward-port chain; others create a single manually-specified env."""
        from cc.base.arm.workspace import Workspace

        workspace = Workspace.find_by(name=workspace_name, limit=1)
        if not workspace:
            log.error(f"Workspace '{workspace_name}' not found.")
            return False

        version = workspace.version_id
        if not version:
            log.error(f"Workspace '{workspace_name}' has no linked version.")
            return False

        if workspace.is_rnd:
            from cc.utils.console import get_console
            get_console().print(
                f"[warning]'{workspace_name}' is an R&D workspace[/] — create R&D projects with "
                f"[primary]cc rnd project {project_name}[/] (needs the cc-rnd plugin)."
            )
            return False
        return self._execute_add_workspace_simple(project_name, workspace, version)

    def _execute_add_workspace_simple(self, project_name, workspace, version):
        """Non-R&D workspace: create a project with a single, manually-set env."""
        import os

        from cc.utils.console import get_console
        console = get_console()

        result = call("project.create", name=project_name)
        if not result:
            log.error(f"Failed to create project '{project_name}'.")
            return False
        project = self.project.find_by(id=result["id"], limit=1)
        call("workspace.assign_project", workspace_id=workspace.id, project_id=project.id)

        env_name = self.prompter.prompt_input_single("Environment name", default=project_name) or project_name

        github_url, branch_name = "", ""
        odoo_path = os.path.join(version.path, self.Constants.ODOO_ODOO)
        if os.path.isdir(odoo_path):
            github_url, branch_name = self._get_branch_details(odoo_path)
        if not branch_name:
            branch_name = self.prompter.prompt_input_single("Branch name", default="") or ""

        db_names = self.Helpers.get_relevant_project_db_names(project_name)
        if db_names:
            db_name = self.prompter.prompt_autocomplete(db_names, "Choose a database")
        else:
            db_name = self.prompter.prompt_input_single("Database name", default=project_name)
        if not db_name:
            db_name = project_name

        call(
            "env.create",
            name=env_name,
            project_id=project.id,
            version_name=version.name,
            version_path=version.path,
            project_path=version.path,
            github_url=github_url,
            branch_name=branch_name,
            database_name=db_name,
            module_names=[],
        )
        console.print(f"[success]✓ Project '{project_name}' created in workspace '{workspace.name}'.[/]")
        console.print(f"  [muted]Environment '{env_name}' ready.[/] Use [primary]cc switch {project_name}[/] to activate.")
        return True

    def _execute_project_remove(self, project_name):
        if not project_name:
            # Interactive selection
            projects = self.project.search([])
            if not projects:
                log.error("No projects to remove.")
                return False
            choices = [p.name for p in projects]
            project_name = self.prompter.prompt_autocomplete(choices, "Select project to remove")

        if not project_name:
            return False

        log.debug(f"Attempting to remove project: {project_name}")
        project = self.project.find_by(name=project_name, limit=1)
        if not project:
            log.error(f"Project with name '{project_name}' not found.")
            return False
        return self._execute_remove(project)

    def _execute_add(self, project: Project = None, environment_name: Optional[str] = None, project_name: Optional[str] = None):
        """
        Add a new environment to a project.

        When called from switch on an unknown alias, pass project_name only —
        the project record is created *after* all prompts succeed so that an
        abort mid-wizard doesn't leave an empty project in the DB.

        When called from `cc project add`, pass an existing project object.
        """
        # Resolve the name we'll search paths with
        search_name = project.name if project else project_name
        if not search_name:
            log.error("No project name provided.")
            return False

        log.debug(f"Searching for project paths matching '{search_name}'")
        # NOTE: args.version here would be the GLOBAL -v/--version boolean
        # (there is no per-command version filter), so pass no filter.
        discovered_paths_map, _versions_config_map = self.Helpers._get_project_paths(
            search_name, ""
        )
        if not discovered_paths_map:
            log.error(f"No project paths found on the filesystem that could match '{search_name}'.")
            log.warning(
                "Ensure the project directories exists and are discoverable, by running 'cc config' to discover versions."
            )
            return False

        # We need a temporary project-like object for the prompt logic.
        # If the project doesn't exist yet, create a stub so prompts can reference project.name.
        # Actual DB write is deferred until all prompts confirm.
        project_created = False
        if not project:
            project = self._create_project(search_name)
            if not project:
                return False
            project_created = True

        name = environment_name or project.name
        log.debug(f"Configuring new environment with name: {name}")
        environment_config = self._select_and_prepare_new_environment_config(name, project, discovered_paths_map)

        if not environment_config:
            # User aborted — clean up the project we just created
            if project_created:
                log.debug(f"Aborting: removing auto-created project '{project.name}'")
                call("project.delete", project_id=project.id)
            from cc.utils.console import get_console
            get_console().print("[muted]Aborted.[/]")
            return False

        environment = self._create_new_environment(environment_config)

        if not environment:
            if project_created:
                call("project.delete", project_id=project.id)
            log.error(f"Failed to save and activate the new configuration for '{name}'.")
            return False

        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Created environment '{environment.name}' for project '{project.name}'.[/]")
        return environment

    def _execute_remove(self, project: Project):
        project_name = project.name
        if not self.args.yes and not self.prompter.prompt_confirm(
            f"Are you sure you want to delete project '{project_name}' and all its environments?",
        ):
            from cc.utils.console import get_console
            get_console().print("[muted]Deletion aborted.[/]")
            return False

        log.debug(f"Deleting project '{project_name}' (ID: {project.id}) and all related environments/modules.")
        call("project.delete", project_id=project.id)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Project '{project_name}' removed.[/]")
        return True

    def set_active_environment(self, env_id: int, version_id: int = None):
        """Persist the active environment via daemon RPC and update local session cache."""
        log.debug(f"Setting active environment id={env_id}")
        from cc.daemon.client import call

        call("env.switch", env_id=env_id, version_id=version_id)

        # Fetch ORM object so post-switch local ops (IDE config, pyenv, git) work unchanged.
        env = self.environment.find_by(id=env_id, limit=1)
        self.__dict__["active_environment"] = env
        self.__dict__["active_project"] = env.project_id
        self.__dict__["active_version"] = env.version_id
        log.debug(f"Active environment set to: {env.name}")

    def _get_timesheet_threshold(self) -> int:
        """Returns the flag threshold in minutes from settings (default 60)."""
        setting = self.setting.find_by(name=self.Constants.SETTING_TIMESHEET_THRESHOLD, limit=1)
        try:
            return int(setting.value) if setting else 60
        except (ValueError, TypeError):
            return 60

    def _create_project(self, project_name: str):
        project = self.project.find_by(name=project_name, limit=1)
        if project:
            from cc.utils.console import get_console
            get_console().print(f"[muted]Project '{project_name}' already exists.[/]")
            return project

        from cc.utils.console import get_console
        get_console().print(f"[muted]Creating new project: '{project_name}'[/]")
        result = call("project.create", name=project_name)
        if not result:
            log.error(f"Failed to create project '{project_name}'.")
            return False
        return self.project.find_by(id=result["id"], limit=1)

    def _create_new_environment(self, config: EnvironmentConfig) -> Environment:
        log.debug(f"Creating new environment record for: {config.name}")
        result = call(
            "env.create",
            name=config.name,
            project_id=config.project.id,
            version_name=config.version_name,
            version_path=config.version_path,
            project_path=config.project_path,
            github_url=config.github_url,
            branch_name=config.branch_name,
            database_name=config.database_name,
            module_names=config.module_ids or [],
        )
        if not result:
            log.error(f"Failed to create new environment for '{config.name}'.")
            return False
        return self.environment.find_by(id=result["id"], limit=1)

    def _select_and_prepare_new_environment_config(
        self,
        name: str,
        project: Project,
        discovered_paths_map: dict,
    ) -> Optional[EnvironmentConfig]:
        """
        Helper to select a project path from discovered paths and get DB info.
        Returns a dictionary with {project_path, version_path, version_name, db_name} or None.
        """
        chosen_project_path = None
        chosen_version_info = None

        if len(discovered_paths_map) == 1:
            chosen_project_path = list(discovered_paths_map.keys())[0]
            chosen_version_info = discovered_paths_map[chosen_project_path]
            from cc.utils.console import get_console
            get_console().print(f"[muted]Auto-selected discovered path: {chosen_project_path}[/]")
        else:
            display_choices_map: Dict[str, str] = {}
            display_choices = []
            for path_key, (_ver_path, ver_name) in discovered_paths_map.items():
                display_str = f"{path_key} (Version: {ver_name or 'Unknown'})"
                display_choices.append(display_str)
                display_choices_map[display_str] = path_key

            chosen_display_string = self.prompter.prompt_input_multi(
                display_choices,
                f"Multiple potential paths found for {name}. Choose one:",
            )
            chosen_project_path = display_choices_map.get(chosen_display_string)
            if chosen_project_path:
                chosen_version_info = discovered_paths_map[chosen_project_path]
            else:
                log.error("Selection mapping failed. Inconsistent choice from prompt.")
                return None

        if not chosen_project_path or not chosen_version_info:
            log.error("Could not determine project path or version from selection.")
            return None

        chosen_version_path, chosen_version_name = chosen_version_info
        log.debug(f"Selected path: {chosen_project_path}")
        log.debug(f"Selected version: {chosen_version_name} ({chosen_version_path})")

        # --- Select Github Repo Branch --- #
        log.debug("Getting branch details...")
        github_url, branch_name = self._get_branch_details(chosen_project_path)

        # --- Select a PSQL Database --- #
        log.debug("Finding relevant database names...")
        db_names = self.Helpers.get_relevant_project_db_names(project.name)
        chosen_db_name = None

        if not db_names:
            log.warning(f"Could not find any relevant PostgreSQL databases for project '{project.name}'.")
            chosen_db_name = self.prompter.prompt_input_single(
                "Enter custom database name: ", default=project.name
            )
        else:
            chosen_db_name = self.prompter.prompt_autocomplete(
                db_names,
                "Choose a Database",
            )

        if not chosen_db_name:
            log.warning(f"No database name provided. Auto assigning to {project.name}")
            chosen_db_name = project.name
        log.debug(f"Selected database: {chosen_db_name}")

        module_names, submodule_names = self.Helpers.get_all_project_modules(chosen_project_path)
        module_names = sorted(module_names | submodule_names)
        log.debug(f"Found {len(module_names)} modules. Prompting for selection.")
        chosen_module_names = self.prompter.prompt_checkbox(
            module_names,
            "Choose Modules for Environment",
        )
        if not chosen_module_names:
            chosen_module_names = []
        else:
            log.debug(f"Selected {len(chosen_module_names)} modules.")

        return EnvironmentConfig(
            name=name,
            project=project,
            project_path=chosen_project_path,
            version_path=chosen_version_path,
            version_name=chosen_version_name,
            database_name=chosen_db_name,
            module_ids=chosen_module_names,
            github_url=github_url,
            branch_name=branch_name,
        )
