import logging
import webbrowser

from cc.base.arm import Project
from cc.base.command import Command
from cc.utils.console import get_console

log = logging.getLogger("CC")


class PsxCommand(Command):
    name = "psx"
    description = "Open the PSX runbot tests for the active branch in a browser."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Open psxrunbot for a specific project: cc psx PROJECT_NAME",
                nargs="?",
                complete=Project,
            ),
        ]

        return arguments

    def execute(self):
        log.debug(f"Executing psx command with args: {self.args}")
        branch_name = self.get_branch_name_from_env()
        return self._open_psx_runbot(branch_name)

    def _open_psx_runbot(self, branch_name):
        if not branch_name:
            log.error("No valid branch name found for the environment.")
            return False

        # Configurable via psx.url_template ({branch} placeholder); the default
        # targets Odoo's PS runbot.
        setting = self.setting.find_by(name=self.Constants.SETTING_RUNBOT_URL, limit=1)
        template = (setting.value.strip() if setting and setting.value else "") \
            or "https://psxrunbot.odoo.com/runbot/bundle/{branch}"
        url = template.format(branch=branch_name)
        console = get_console()
        console.print(f"[muted]Opening psxrunbot URL in browser: {url}[/]")

        try:
            if not webbrowser.open(url):
                log.warning("webbrowser.open() returned False. Could not determine how to open the URL.")
                return False
            return True
        except Exception as e:
            log.error(f"Failed to open web browser: {e}")
            return False

    def get_branch_name_from_env(self):
        """
        Gets the branch_name from the active environment or a selected environment.
        """
        environment = None
        if self.args.name:
            # Project name is specified, find it and select environment
            project_id = self.project.find_by(name=self.args.name, limit=1)
            if not project_id:
                log.error(f"No valid project found with name: '{self.args.name}'")
                return False

            log.debug(f"Found project '{project_id.name}', selecting environment.")
            environment = self.project_environment_selector(project_id)
            if not environment:
                log.error(f"No environment selected for project '{project_id.name}'.")
                return False
        else:
            # No project name, use active environment
            log.debug("No project name specified, using active environment.")
            environment = self.active_environment
            if not environment:
                log.error("No active environment found. Please specify a project name or run 'cc switch' first.")
                return False

        branch_name = environment.branch_name
        if not branch_name:
            log.warning(f"The selected environment '{environment.name}' has no branch_name configured.")
            console = get_console()
            console.print("[warning]No branch configured.[/] Run [primary]cc git branch[/]")
            return False

        log.debug(f"Using branch from environment '{environment.name}': '{branch_name}'")
        return branch_name
