"""`cc project create | list | delete` — the project CRUD verbs.

Split out of the ProjectCommand base (which is also the shared base for
env/open/switch/stat) so `project` can be a noun group. Each verb reuses the
base's _execute_project_* helpers.
"""
from cc.base.arm import Project
from cc.commands.project.project_command import ProjectCommand
from cc.daemon.client import call
from cc.utils.console import get_console


class ProjectCreateCommand(ProjectCommand):
    group = "project"
    name = "create"
    description = "Create a project."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", complete=Project, help="Project name."),
            self.Argument(["-y", "--yes"], action="store_true", help="Skip confirmation prompt."),
            self.Argument(["--virtual"], action="store_true",
                          help="Create a virtual project (no local path, time tracking only)."),
            self.Argument(["-w", "--workspace"], type=str, default=None,
                          help="Create the project in a workspace."),
        ]

    def execute(self):
        return self._execute_project_add(self.args.name)


class ProjectListCommand(ProjectCommand):
    group = "project"
    name = "list"
    description = "List projects."

    def arguments(self):
        return []

    def execute(self):
        return self._execute_list()


class ProjectDeleteCommand(ProjectCommand):
    group = "project"
    name = "delete"
    description = "Delete a project and all its environments."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", complete=Project, help="Project to delete."),
            self.Argument(["-y", "--yes"], action="store_true", help="Skip confirmation prompt."),
        ]

    def execute(self):
        return self._execute_project_remove(self.args.name)


class ProjectKeepCommand(ProjectCommand):
    group = "project"
    name = "keep"
    description = "Exempt a project from auto-archiving (toggle); its envs won't go stale."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", complete=Project, help="Project to keep / un-keep."),
        ]

    def execute(self):
        console = get_console()
        name = self.args.name
        if not name:
            name = self.prompter.prompt_autocomplete(self.project.search([]).mapped("name"), "Choose Project")
            if not name:
                return False
        project = self.project.find_by(name=name, limit=1)
        if not project:
            console.print(f"[error]Project '{name}' not found.[/]")
            return False
        # toggle the current flag (NULL → exempt on)
        exempt = not bool(project.no_auto_archive)
        result = call("project.set_auto_archive", project_id=project.id, exempt=exempt)
        if result["no_auto_archive"]:
            console.print(f"[success]✓ '{result['name']}' is now kept[/] — exempt from auto-archiving.")
        else:
            console.print(f"[muted]'{result['name']}' is no longer exempt[/] — auto-archiving applies again.")
        return True
