import logging

from cc.base.arm import Workspace
from cc.base.command import Command
from cc.daemon.client import call

log = logging.getLogger("CC")


class WorkspaceCommand(Command):
    name = "workspace"
    description = "Manage workspaces — groups of projects sharing an Odoo version (add, list, edit, open, remove)."

    def arguments(self):
        return [
            self.Argument(
                names=["action"],
                type=str,
                nargs="?",
                choices=["add", "list", "edit", "open", "assign", "remove"],
                help="Action to perform.",
                default="list",
            ),
            self.Argument(
                names=["name"],
                type=str,
                nargs="?",
                help="Workspace name.",
                complete=Workspace,
            ),
            self.Argument(
                names=["-n", "--new"],
                action="store_true",
                help="Open in new VS Code window (with 'open').",
            ),
        ]

    def execute(self):
        action = self.args.action
        name = self.args.name

        if action == "add":
            return self._execute_add(name)
        elif action == "list":
            return self._execute_list()
        elif action == "edit":
            return self._execute_edit(name)
        elif action == "open":
            return self._execute_open(name)
        elif action == "assign":
            return self._execute_assign(name)
        elif action == "remove":
            return self._execute_remove(name)

        self.parser.print_help()
        return False

    def _execute_list(self):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table

        workspaces = call("workspace.get_all")
        if not workspaces:
            from cc.utils.console import get_console
            get_console().print("[warning]No workspaces found.[/] Run [primary]cc workspace add[/] or [primary]cc config[/] to get started.")
            return True

        versions = {v.id: v for v in self.version.search([])}
        console = get_console()

        table = themed_table(title="Workspaces")
        table.add_column("Name", style="bold")
        table.add_column("R&D", style="warning")
        table.add_column("Version", style="primary")
        table.add_column("Path", style="branch", overflow="fold")
        table.add_column("Port", justify="right")
        table.add_column("Branch")

        for w in workspaces:
            rnd = ""
            if w.get("is_rnd"):
                fork = w.get("fork_remote", "origin")
                upstream = w.get("upstream_remote", "odoo")
                rnd = f"{fork}↔{upstream}"

            v = versions.get(w.get("version_id"))
            if v:
                table.add_row(
                    w["name"], rnd, v.name, v.path or "",
                    str(v.port or ""), v.branch or "",
                )
            else:
                table.add_row(
                    w["name"], rnd, "", w.get("path") or "", "", "",
                )

        console.print()
        console.print(table)
        console.print()
        return True

    def _execute_add(self, name):
        if not name:
            name = self.prompter.prompt_input_single("Workspace name")
        if not name:
            return False

        versions = self.version.search([])
        version_names = [v.name for v in versions]
        version_id = 0
        if version_names:
            version_name = self.prompter.prompt_autocomplete(
                version_names, "Link to version (optional, Enter to skip)"
            )
            if version_name:
                v = self.version.find_by(name=version_name, limit=1)
                version_id = v.id if v else 0

        path = self.prompter.prompt_input_path(
            "Workspace path (optional, Enter to skip)", default="",
            allow_empty=True, must_exist=True, kind="dir",
        ) or ""
        is_rnd = self.prompter.prompt_confirm("Is this an R&D workspace?", default=False)

        fork_remote = ""
        upstream_remote = ""
        if is_rnd:
            fork_remote = self.prompter.prompt_input_single("Fork remote name", default="origin") or "origin"
            upstream_remote = self.prompter.prompt_input_single("Upstream remote name", default="odoo") or "odoo"

        call("workspace.create", name=name, path=path, is_rnd=is_rnd,
             fork_remote=fork_remote, upstream_remote=upstream_remote, version_id=version_id)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Workspace '{name}' created.[/]")

        self._maybe_run_ide_setup(version_id)
        return True

    def _maybe_run_ide_setup(self, version_id: int) -> None:
        """Offer to write IDE debugger templates for the linked version's path.

        This is the one-shot ``setup()`` half of the IDE writer contract — it
        only ever runs here (or via the explicit ``cc config ide setup`` command).
        ``cc switch`` never touches launch.json.
        """
        if not version_id:
            return
        v = self.version.find_by(id=version_id, limit=1)
        if not v or not v.path:
            return

        from pathlib import Path

        from cc.ide import active_writers
        from cc.utils.console import get_console

        workspace = Path(v.path)
        writers = active_writers(workspace)
        if not writers:
            return

        names = ", ".join(w.name for w in writers)
        if not self.prompter.prompt_confirm(
            f"Write debugger templates now for {names}? (run later with: cc config ide setup)",
            default=True,
        ):
            return

        console = get_console()
        for writer in writers:
            try:
                writer.setup(workspace)
                console.print(f"[success]✓[/] [primary]{writer.name}[/] templates written → {workspace}")
            except Exception as e:
                console.print(f"[error]✗[/] [primary]{writer.name}[/] setup failed: {e}")

    def _execute_edit(self, name):
        workspace = self._resolve_workspace(name)
        if not workspace:
            return False

        from cc.utils.console import get_console
        console = get_console()

        options = ["Name", "Path", "Version", "Port", "R&D flag", "Fork remote", "Upstream remote"]
        choice = self.prompter.prompt_input_multi(options, "Choose field to edit")
        if not choice:
            return False

        if choice == "Name":
            new_name = self.prompter.prompt_input_single("New name", default=workspace["name"])
            if new_name and new_name != workspace["name"]:
                call("workspace.update", workspace_id=workspace["id"], name=new_name)
                console.print(f"[success]✓ Renamed to '{new_name}'.[/]")

        elif choice == "Path":
            current = workspace.get("path", "")
            new_path = self.prompter.prompt_input_path("New path", default=current, must_exist=True, kind="dir")
            if new_path and new_path != current:
                call("workspace.update", workspace_id=workspace["id"], path=new_path)
                console.print("[success]✓ Path updated.[/]")

        elif choice == "Version":
            versions = self.version.search([])
            version_names = [v.name for v in versions]
            current = workspace.get("version_name", "")
            version_name = self.prompter.prompt_autocomplete(version_names, "Select version", default=current)
            if version_name:
                v = self.version.find_by(name=version_name, limit=1)
                if v:
                    call("workspace.update", workspace_id=workspace["id"], version_id=v.id)
                    console.print(f"[success]✓ Linked to version '{version_name}'.[/]")

        elif choice == "Port":
            v_id = workspace.get("version_id")
            if not v_id:
                console.print("[warning]No linked version. Link a version first to set its port.[/]")
                versions = self.version.search([])
                version_names = [v.name for v in versions]
                if not version_names:
                    console.print("[error]No versions registered. Run 'cc setup' first.[/]")
                    return False
                version_name = self.prompter.prompt_autocomplete(version_names, "Select version")
                if not version_name:
                    return False
                v = self.version.find_by(name=version_name, limit=1)
                if not v:
                    return False
                call("workspace.update", workspace_id=workspace["id"], version_id=v.id)
                v_id = v.id
                console.print(f"[success]✓ Linked to version '{version_name}'.[/]")
            v = self.version.find_by(id=v_id, limit=1)
            current_port = v.port if v else "8069"
            new_port = self.prompter.prompt_input_single("Port", default=current_port or "8069")
            if new_port and new_port != current_port:
                call("version.update_port", version_id=v_id, port=new_port)
                console.print(f"[success]✓ Port updated to {new_port}.[/]")

        elif choice == "R&D flag":
            is_rnd = self.prompter.prompt_confirm(
                "Mark as R&D workspace?", default=workspace.get("is_rnd", False)
            )
            call("workspace.update", workspace_id=workspace["id"], is_rnd=is_rnd)
            console.print("[success]✓ R&D flag updated.[/]")

        elif choice == "Fork remote":
            current = workspace.get("fork_remote", "origin")
            new_val = self.prompter.prompt_input_single("Fork remote name", default=current)
            if new_val:
                call("workspace.update", workspace_id=workspace["id"], fork_remote=new_val)
                console.print(f"[success]✓ Fork remote set to '{new_val}'.[/]")

        elif choice == "Upstream remote":
            current = workspace.get("upstream_remote", "odoo")
            new_val = self.prompter.prompt_input_single("Upstream remote name", default=current)
            if new_val:
                call("workspace.update", workspace_id=workspace["id"], upstream_remote=new_val)
                console.print(f"[success]✓ Upstream remote set to '{new_val}'.[/]")

        return True

    def _execute_open(self, name):
        workspace = self._resolve_workspace(name)
        if not workspace:
            return False

        v_id = workspace.get("version_id")
        path = None

        if v_id:
            v = self.version.find_by(id=v_id, limit=1)
            path = v.path if v else None

        if not path:
            path = workspace.get("path")

        if not path:
            log.error("Workspace has no path or linked version to open.")
            return False

        from cc.utils.console import get_console
        get_console().print(f"[muted]Opening VS Code for workspace '{workspace['name']}' at {path}[/]")
        return self.Helpers.vs_code(path, "config_files", new_window=self.args.new)

    def _execute_assign(self, name):
        workspace = self._resolve_workspace(name)
        if not workspace:
            return False

        projects = call("project.get_all")
        if not projects:
            log.error("No projects found.")
            return False

        chosen = self.prompter.prompt_input_multi(projects, "Select project to assign")
        if not chosen:
            return False

        project = self.project.find_by(name=chosen, limit=1)
        if not project:
            log.error(f"Project '{chosen}' not found.")
            return False

        call("workspace.assign_project", workspace_id=workspace["id"], project_id=project.id)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Project '{chosen}' assigned to workspace '{workspace['name']}'.[/]")
        return True

    def _execute_remove(self, name):
        workspace = self._resolve_workspace(name)
        if not workspace:
            return False

        if not self.prompter.prompt_confirm(
            f"Delete workspace '{workspace['name']}'? Projects will be unlinked, versions are kept."
        ):
            return False

        call("workspace.delete", workspace_id=workspace["id"])
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Workspace '{workspace['name']}' removed.[/]")
        return True

    def _resolve_workspace(self, name):
        workspaces = call("workspace.get_all")
        if not workspaces:
            log.error("No workspaces found.")
            return None

        if name:
            match = next((w for w in workspaces if w["name"] == name), None)
            if not match:
                log.error(f"Workspace '{name}' not found.")
            return match

        names = [w["name"] for w in workspaces]
        chosen = self.prompter.prompt_input_multi(names, "Select workspace")
        if not chosen:
            return None
        return next((w for w in workspaces if w["name"] == chosen), None)
