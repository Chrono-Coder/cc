import logging

from cc.completion.kinds import CompleteKind
from cc.daemon.client import call

from .project_command import ProjectCommand

log = logging.getLogger("CC")

# Old verbs kept working as silent aliases (not advertised / not completed).
_ENV_ALIASES = {"add": "create", "remove": "delete"}


class EnvironmentCommand(ProjectCommand):
    group = "project"   # explicit: own-attr group doesn't inherit from ProjectCommand
    name = "env"
    description = "Manage project environments (create, list, delete, edit, archive, activate, merged)."

    def arguments(self):
        return [
            # Positional action. No argparse choices= so old verbs (add/remove)
            # still work as silent aliases; the completer offers only the
            # canonical verbs, and execute() rejects anything unknown.
            self.Argument(
                names=["action"],
                type=str,
                nargs="?",
                complete=("create", "list", "delete", "edit", "archive", "activate", "merged", "pin", "unpin"),
                help="Action: create, list, delete, edit, archive, activate, merged, pin, unpin.",
                default="list",
            ),
            # Optional target — project (create/list) or env name (delete/edit/…).
            self.Argument(
                names=["target"],
                type=str,
                nargs="?",
                help="Project (for list) or environment name (for delete/edit/archive).",
                complete=CompleteKind.ENV_TARGET,
            ),
            self.Argument(
                names=["-y", "--yes"],
                action="store_true",
                help="Skip confirmation prompt.",
            ),
            self.Argument(
                names=["--json"],
                action="store_true",
                help="Output as JSON (list action only).",
            ),
        ]

    def execute(self):
        action = _ENV_ALIASES.get(self.args.action, self.args.action)
        target = self.args.target

        if action == "create":
            return self._execute_env_add(target)
        elif action == "delete":
            return self._execute_env_remove(target)
        elif action == "list":
            return self._execute_list_env(target)
        elif action == "edit":
            return self._execute_env_edit(target)
        elif action in ("archive", "activate", "merged"):
            status = {"archive": "archived", "activate": "active", "merged": "merged"}[action]
            return self._execute_set_status(target, status)
        elif action in ("pin", "unpin"):
            return self._execute_set_pin(target, action == "pin")

        self.parser.print_help()
        return False

    def _execute_set_pin(self, target, pinned):
        env = self._resolve_environment(target, action="pin" if pinned else "unpin")
        if not env:
            return False
        call("env.update", env_id=env.id, pinned=pinned)
        from cc.utils.console import get_console
        get_console().print(
            f"[success]✓ {env.name} {'pinned' if pinned else 'unpinned'}.[/]"
        )
        return True

    def _execute_env_add(self, project_alias):
        if not project_alias:
            # Interactive selection
            project_alias = self.prompter.prompt_autocomplete(self.project.search([]).mapped("name"), "Choose Project")
            if not project_alias:
                return False

        from cc.utils.console import get_console
        get_console().print(f"[muted]Adding environment to project '{project_alias}'...[/]")

        projects = self.project.find_by(name=project_alias, limit=1)
        project = projects[0] if projects else None

        if not project:
            log.error(f"Project '{project_alias}' not found. To create a new project, use 'cc project'.")
            return False

        env_name = self.prompter.prompt_input_single("Environment Name", default=f"{project.name}_env")

        # Reuse existing add logic from parent ProjectCommand if available, or call internal logic
        environment_id = self._execute_add(
            project=project,
            environment_name=env_name,
        )

        if environment_id:
            self._list([environment_id])
            return True
        return False

    def _execute_list_env(self, project_alias=False, active_only=False):
        if project_alias:
            project = self.project.find_by(name=project_alias, limit=1)
            if not project:
                log.error(f"Project '{project_alias}' not found.")
                return False
        else:
            project = self.active_project
            if not project:
                from cc.utils.console import get_console
                get_console().print("[muted]No active project. Listing all environments:[/]")
                all_envs = self.environment.search([])
                if self.args.json:
                    return self._list_json(all_envs)
                self._list(all_envs)
                return True

        environments = project.environment_ids
        if active_only:
            active_env_ids = {s.environment_id.id for s in self.app_state.find_by()}
            environments = environments.filtered(lambda e: e.id in active_env_ids)

        if self.args.json:
            return self._list_json(environments)

        from cc.utils.console import get_console
        get_console().print(f"\nEnvironments for '[primary]{project.name}[/]':")
        self._list(environments)
        return True

    def _list_json(self, environments):
        import json
        active_env_ids = {s.environment_id.id for s in self.app_state.find_by()}
        out = [
            {
                "name": env.name,
                "project": env.project_id.name,
                "is_active": env.id in active_env_ids,
                "project_path": env.project_path,
                "version": env.version_id.name if env.version_id else None,
                "database": env.database_id.name if env.database_id else None,
                "branch": env.branch_name,
                "github_url": env.github_url,
                "sh_url": env.sh_url,
                "last_used_at": env.last_used_at,
                "status": env.status or "active",
                "modules": [m.name for m in env.module_ids],
            }
            for env in environments
        ]
        print(json.dumps(out, indent=2))
        return True

    def _execute_set_status(self, target, status):
        """Set an env's lifecycle status (active/merged/archived).

        Resolves the env the same way edit/remove do (project alias → picker, or
        the active project). Merged/archived envs drop out of the default switch
        picker; `cc switch --all` still shows them.
        """
        env = self._resolve_environment(target, action=status)
        if not env:
            return False
        result = call("env.set_status", env_id=env.id, status=status)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ {result['name']} → {result['status']}[/]")
        return True

    def _execute_env_remove(self, target_env_name):
        env = self._resolve_environment(target_env_name, action="remove")
        if not env:
            return False

        from cc.utils.console import get_console
        console = get_console()

        if not (self.args.yes or self.prompter.prompt_confirm(
            f"Delete environment '{env.name}'? (modules and switch history will be removed)"
        )):
            return False

        # Note the linked DB (and whether another env shares it) *before* deleting.
        db_name, shared = self._linked_db_for_drop(env)

        call("env.delete", env_id=env.id)
        console.print("[success]✓ Environment deleted.[/]")

        # Dropping the real PG database is a separate, explicit consent — never for a shared DB or under --yes.
        if db_name and not shared and not self.args.yes and self.prompter.prompt_confirm(
            f"Also drop the PostgreSQL database '{db_name}'? This destroys real data and cannot be undone."
        ):
            try:
                call("database.drop", name=db_name)
                console.print(f"[success]✓ Dropped database '{db_name}'[/]")
            except Exception as e:
                console.print(f"[error]Couldn't drop '{db_name}':[/] {e}")
        return True

    def _linked_db_for_drop(self, env):
        """(db_name, shared) for the env's active DB — shared=True if another env also points at it."""
        from cc.base.arm.environment import Environment
        from cc.base.db import database_connection_manager
        with database_connection_manager():
            e = Environment.search([("id", "=", env.id)], limit=1)
            if not e or not e.database_id:
                return None, False
            db = e.database_id
            others = [o for o in Environment.search([("database_id", "=", db.id)]) if o.id != e.id]
            return db.name, bool(others)

    def _execute_env_edit(self, target_env_name):
        env = self._resolve_environment(target_env_name, action="edit")
        if not env:
            return False

        from cc.utils.console import get_console
        console = get_console()
        console.print(f"[muted]Editing Environment: {env.name}[/]")

        options = ["Name", "Branch", "Database", "Version", "Modules", "GitHub URL", "Tickets", "Notes", "Project path", "SSH Tunnel", "Status"]
        choice = self.prompter.prompt_input_multi(options, "Choose field to edit")

        if not choice:
            return False

        if choice == "Name":
            new_name = self.prompter.prompt_input_single("New Name", default=env.name)
            if new_name and new_name != env.name:
                call("env.update", env_id=env.id, name=new_name)
                console.print(f"[success]✓ Updated name to: {new_name}[/]")

        elif choice == "Branch":
            current = env.branch_name or ""
            new_branch = self.prompter.prompt_input_single("Branch name", default=current)
            if new_branch is not None and new_branch != current:
                call("env.update", env_id=env.id, branch_name=new_branch)
                console.print(f"[success]✓ Updated branch to: {new_branch}[/]")

        elif choice == "Version":
            versions = self.version.search([])
            version_names = [v.name for v in versions]
            current = env.version_id.name if env.version_id else ""
            version_name = self.prompter.prompt_autocomplete(version_names, "Select version", default=current)
            if version_name:
                v = self.version.find_by(name=version_name, limit=1)
                if v:
                    call("env.update", env_id=env.id, version_id=v.id)
                    console.print(f"[success]✓ Updated version to: {version_name}[/]")

        elif choice == "GitHub URL":
            current = env.github_url or ""
            new_url = self.prompter.prompt_input_single("GitHub URL", default=current)
            if new_url is not None and new_url != current:
                call("env.update", env_id=env.id, github_url=new_url)
                console.print("[success]✓ Updated GitHub URL.[/]")

        elif choice == "Tickets":
            current = env.ticket_ids or ""
            new_tickets = self.prompter.prompt_input_single("Ticket IDs (comma-separated)", default=current)
            if new_tickets is not None and new_tickets != current:
                cleaned = ",".join(t.strip() for t in new_tickets.split(",") if t.strip())
                call("env.update", env_id=env.id, ticket_ids=cleaned)
                console.print("[success]✓ Updated tickets.[/]")

        elif choice == "Notes":
            current = env.notes or ""
            new_notes = self.prompter.prompt_input_single("Notes", default=current)
            if new_notes is not None:
                call("env.update", env_id=env.id, notes=new_notes)
                console.print("[success]✓ Updated notes.[/]")

        elif choice == "Project path":
            current = env.project_path or ""
            new_path = self.prompter.prompt_input_path("Project path", default=current, must_exist=True, kind="dir")
            if new_path and new_path != current:
                call("env.update", env_id=env.id, project_path=new_path)
                console.print("[success]✓ Updated project path.[/]")

        elif choice == "Database":
            # Fetch relevant databases
            db_names = self.Helpers.get_relevant_project_db_names(env.project_id.name)
            current_db = env.database_id.name if env.database_id else ""

            # Add current to list if missing
            if current_db and current_db not in db_names:
                db_names.append(current_db)

            # Autocomplete selection
            new_db_name = self.prompter.prompt_autocomplete(db_names, "Select Database")

            if new_db_name and new_db_name != current_db:
                db_record = self.database.find_by(name=new_db_name, limit=1)
                if not db_record:
                    if self.prompter.prompt_confirm(f"Database '{new_db_name}' not in registry. Create it?"):
                        db_id = call("database.create", name=new_db_name)
                    else:
                        return False
                else:
                    db_id = db_record.id
                call("env.update", env_id=env.id, database_id=db_id)
                console.print(f"[success]✓ Updated database to: {new_db_name}[/]")

        elif choice == "Modules":
            # Multi-select for modules
            project_path = env.project_path
            module_names, _ = self.Helpers.get_all_project_modules(project_path)
            module_names = sorted(module_names)

            # Get current modules
            current_modules = [m.name for m in env.module_ids]

            console.print(f"[muted]Current modules: {', '.join(current_modules)}[/]")
            new_selection = self.prompter.prompt_checkbox(module_names, "Select Modules")

            if new_selection is not None:  # Empty list is valid clearing
                formatted_modules = [(0, 0, {"name": m}) for m in new_selection]
                call("env.update_modules", env_id=env.id, module_ids=formatted_modules)
                console.print(f"[success]✓ Updated modules: {len(new_selection)} selected.[/]")

        elif choice == "Status":
            from cc.services.environment import ENV_STATUSES
            current = env.status or "active"
            new_status = self.prompter.prompt_input_multi(
                list(ENV_STATUSES), f"Select status (current: {current})"
            )
            if new_status and new_status != current:
                call("env.set_status", env_id=env.id, status=new_status)
                console.print(f"[success]✓ Status → {new_status}[/]")

        elif choice == "SSH Tunnel":
            new_host = self.prompter.prompt_input_single("SSH Host", default=env.ssh_host or "")
            new_user = self.prompter.prompt_input_single("SSH User", default=env.ssh_user or "")
            updates = {}
            if new_host:
                updates["ssh_host"] = new_host
            if new_user:
                updates["ssh_user"] = new_user
            if updates:
                call("env.update", env_id=env.id, **updates)
                console.print("[success]✓ SSH Tunnel config updated.[/]")

        return True

    def _resolve_environment(self, target, action="edit"):
        """Resolve the env to act on for delete/edit/archive.

        `target` is an ENVIRONMENT name first; since names are non-unique, a
        cross-project collision pops a project/env picker rather than silently
        taking the first match. Falls back to treating `target` as a project
        alias (pick among its envs) for back-compat. With no target, picks among
        the active project's envs.
        """
        if target:
            matches = self.environment.search([("name", "=", target)])
            if matches:
                return matches[0] if len(matches) == 1 else self._pick_by_project(matches)
            # Back-compat: maybe they passed a project alias.
            project = self.project.find_by(name=target, limit=1)
            if project:
                return self.project_environment_selector(project)
            log.error(f"No environment or project named '{target}'.")
            return None

        # No target specified — pick among the active project's envs.
        if self.active_project:
            envs = list(self.active_project.environment_ids)
            if not envs:
                log.error("Active project has no environments.")
                return None
            if len(envs) == 1:
                return envs[0]
            name = self.prompter.prompt_input_multi([e.name for e in envs], f"Select environment to {action}")
            return next((e for e in envs if e.name == name), None) if name else None

        log.error(f"Please specify an environment name to {action}.")
        return None
