"""Interactive Odoo server and shell commands."""

import logging
import subprocess

from cc.base.command import Command
from cc.runtime import OdooRuntime
from cc.utils.console import get_console
from cc.utils.errors import CCError

log = logging.getLogger("CC")


class _RunCommand(Command):
    def arguments(self):
        return [
            self.Argument(["--database", "-d"], type=str, help="Override the active database."),
            self.Argument(
                ["extra_args"], nargs="*", help="Additional arguments passed to odoo-bin (use -- first)."
            ),
        ]

    def _run(self, mode: str, dev: bool = True) -> bool:
        try:
            runtime = OdooRuntime.from_command(self, database=self.args.database)
            argv = runtime.command(mode, self.args.extra_args, dev=dev)
        except CCError as exc:
            log.error(str(exc))
            return False

        get_console().print(
            f"[muted]Starting Odoo {mode} for database[/] [db]{runtime.database}[/]"
        )
        try:
            return subprocess.run(argv, cwd=runtime.cwd).returncode == 0
        except OSError as exc:
            log.error(f"Could not start Odoo: {exc}")
            return False


class RunServerCommand(_RunCommand):
    group = "run"
    name = "server"
    description = "Start the Odoo server for the active environment."

    def arguments(self):
        return [
            self.Argument(["--database", "-d"], type=str, help="Override the active database."),
            self.Argument(["--no-dev"], action="store_true", help="Do not pass --dev=all."),
            self.Argument(
                ["extra_args"], nargs="*", help="Additional arguments passed to odoo-bin (use -- first)."
            ),
        ]

    def execute(self):
        return self._run("server", dev=not self.args.no_dev)


class RunShellCommand(_RunCommand):
    group = "run"
    name = "shell"
    description = "Open an interactive Odoo shell for the active environment."

    def execute(self):
        return self._run("shell")
