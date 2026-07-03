import logging
import os
import shutil
import subprocess

from cc.base.arm import Project

from .project_command import ProjectCommand

log = logging.getLogger("CC")


class OpenCommand(ProjectCommand):
    group = "project"   # explicit; SwitchCommand(OpenCommand) stays flat (own-attr)
    name = "open"
    description = "Opens a project."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                nargs="?",
                help="Project to open. Omit to open the active environment.",
                complete=Project,
            ),
            self.Argument(
                ["-n", "--new"],
                help="Open in a new IDE window.",
                action="store_true",
            ),
        ]
        return arguments

    def execute(self):
        log.debug(f"Executing open command with args: {self.args}")
        project_name = self.args.name
        project = None
        environment = None

        if not project_name:
            # No arg → open the active environment (no need to retype its project).
            environment = self.active_environment
            if not environment:
                log.error("No project given and no active environment. Run cc switch first.")
                return False
            self._open_ide(environment)
            return True

        project = self.project.find_by(name=project_name, limit=1)
        if project:
            log.debug(f"Project '{project_name}' found. Selecting environment.")
            environment = self.project_environment_selector(project)
        else:
            log.warning(f"Project alias '{project_name}' not found in the database.")
            project = self._create_project(project_name)
            if not project:
                return False
            environment = self._execute_add(project=project, environment_name=project_name)

        if not environment:
            log.error("Could not determine an environment to open.")
            return False

        self._open_ide(environment)
        return True

    def _get_ide_preference(self) -> str:
        """Fetches the configured IDE from settings, defaulting to 'code'."""
        ide_setting = self.setting.find_by(name="ide")
        ide = ide_setting[0].value if ide_setting else "code"
        log.debug(f"Using preferred IDE: {ide}")
        return ide

    def _find_pycharm_launcher(self) -> str:
        """Finds the pycharm or charm command-line launcher."""
        log.debug("Searching for PyCharm launcher ('charm' or 'pycharm')...")
        for launcher in ["charm", "pycharm"]:
            if shutil.which(launcher):
                log.debug(f"Found launcher: {launcher}")
                return launcher
        log.warning("Could not find 'pycharm' or 'charm' launcher in PATH.")
        return None

    def _get_module_to_upgrade(self, project):
        files_changed = self.Helpers.git_get_latest_changed_files(project)
        res = ""
        if files_changed:
            res = files_changed[0].split(os.path.sep)[0]
            log.debug(f"Determined module with latest changes: {res}")
        else:
            log.debug("No changed files found in git history.")

        return res

    def _open_ide(self, environment=None):
        """Opens the active project in the configured IDE."""
        ide = self._get_ide_preference()
        if not environment:
            environment = self.active_environment
            if not environment:
                log.error("Cannot open IDE: No environment specified and no active environment found.")
                return

        path = environment.project_path
        new_window = self._will_open_new_window() if hasattr(self, "_will_open_new_window") else self.args.new

        from cc.utils.console import get_console
        get_console().print(f"[muted]Opening '{environment.project_id.name}' in {ide.capitalize()}...[/]")

        try:
            if ide == "pycharm":
                launcher = self._find_pycharm_launcher()
                if launcher:
                    log.debug(f"Running command: {launcher} {path}")
                    subprocess.run([launcher, path], check=True)
            else:
                module_upgrade_list = [self._get_module_to_upgrade(path)]
                main_focus_component = os.path.basename(path)
                if module_upgrade_list and module_upgrade_list[0]:
                    main_focus_component = module_upgrade_list[0]
                log.debug(f"Setting focus component for VS Code to: {main_focus_component}")

                self.Helpers.vs_code(
                    environment.version_id.path,
                    subdir_to_focus=main_focus_component,
                    new_window=new_window,
                    focus_path=path,
                    ide=ide,
                )
        except Exception as e:
            log.error(f"An error occurred while trying to open the IDE: {e}")
