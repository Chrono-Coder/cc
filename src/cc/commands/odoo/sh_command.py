import logging
import webbrowser

from cc.base.arm import Environment
from cc.base.command import Command
from cc.utils.console import get_console

log = logging.getLogger("CC")


class ShCommand(Command):
    name = "sh"
    description = "Open the active environment's Odoo.sh project in a browser."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                type=str,
                help="Open the Odoo.sh project in the browser: cc sh [NAME]",
                nargs="?",
                complete=Environment,
            ),
        ]

    def execute(self):
        log.debug(f"Executing sh command with args: {self.args}")
        env_name = self.args.name

        if env_name:
            env = self.environment.find_by(name=env_name, limit=1)
            if not env:
                log.error(f"Environment '{env_name}' not found.")
                return False
        else:
            env = self.active_environment
            if not env:
                log.error("No environment name specified and no active environment found.")
                console = get_console()
                console.print("[warning]No active environment.[/] Run [primary]cc switch[/]")
                return False

        if env.sh_url:
            url = env.sh_url
            console = get_console()
            console.print(f"[muted]Opening Odoo.sh: {url}[/]")
            try:
                if not webbrowser.open(url):
                    log.warning("webbrowser.open() returned False.")
                    return False
                return True
            except Exception as e:
                log.error(f"Failed to open web browser: {e}")
                return False
        else:
            log.error(f"Environment '{env.name}' does not have an Odoo.sh URL linked.")
            console = get_console()
            console.print("[warning]No Odoo.sh URL linked.[/] Run [primary]cc web[/] and sync from the Settings page.")
