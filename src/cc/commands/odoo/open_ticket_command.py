import logging
import re
import webbrowser

from cc.base.arm import Project
from cc.base.command import Command
from cc.utils.console import get_console

log = logging.getLogger("CC")


class TicketCommand(Command):
    name = "ticket"
    description = "Open the active environment's linked ticket in a browser."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Open Odoo Ticket: cc ticket PROJECT_NAME",
                nargs="?",
                complete=Project,
            ),
        ]

        return arguments

    def execute(self):
        log.debug(f"Executing ticket command with args: {self.args}")
        ticket_id = self.get_ticket_id()
        return self._open_ticket(ticket_id=ticket_id)

    def _open_ticket(self, ticket_id):
        if not ticket_id:
            log.error("No valid ticket ID found.")
            return False

        # Configurable via ticket.url_template ({ticket} placeholder) so any
        # tracker works; the default targets Odoo's project app.
        setting = self.setting.find_by(name=self.Constants.SETTING_TICKET_URL, limit=1)
        template = (setting.value.strip() if setting and setting.value else "") \
            or "https://www.odoo.com/odoo/project.task/{ticket}"
        url = template.format(ticket=ticket_id)
        console = get_console()
        console.print(f"[muted]Opening ticket URL in browser: {url}[/]")

        try:
            if not webbrowser.open(url):
                log.warning("webbrowser.open() returned False. Could not determine how to open the URL.")
                return False
            return True
        except Exception as e:
            log.error(f"Failed to open web browser: {e}")
            return False

    def get_ticket_id(self):
        # Resolve the environment: explicit project → picker; otherwise active.
        environment = None
        if self.args.name:
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
            environment = self.active_environment

        # Prefer the env's explicit ticket_ids over guessing from the branch.
        if environment and getattr(environment, "ticket_ids", None):
            tickets = [t.strip() for t in environment.ticket_ids.split(",") if t.strip()]
            if len(tickets) == 1:
                return tickets[0]
            if len(tickets) > 1:
                choice = self.prompter.prompt_input_multi(tickets, "Which ticket?")
                return choice or False

        # Fall back to extracting the ticket number from the branch name.
        branch_name = environment.branch_name if environment else self.Helpers.git_get_branch_name()
        if branch_name:
            match = re.search(r"(?:\d+\.\d+-)?(\d+)", branch_name)
            if match:
                ticket_id = match.group(1)
                log.debug(f"Found ticket ID '{ticket_id}' from branch '{branch_name}'")
                return ticket_id
            log.warning(f"Branch '{branch_name}' does not contain a ticket ID.")
            return False
        log.warning("No ticket_ids set and no branch name could be determined.")
        return False
