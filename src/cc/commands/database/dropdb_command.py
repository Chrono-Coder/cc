import logging

from cc.base.arm import Database
from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.console import get_console

log = logging.getLogger("CC")


class DropdbCommand(Command):
    group = "db"
    name = "drop"
    description = "Drop PostgreSQL database(s) (works with dockerized PG; unlinks from envs)."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                type=str,
                nargs="?",
                help="Database to drop. Omit to pick several from a list.",
                complete=Database,
            ),
            self.Argument(
                ["-y", "--yes"],
                action="store_true",
                help="Skip the confirmation prompt.",
            ),
        ]

    def execute(self):
        console = get_console()
        if self.args.name:
            return self._drop([self.args.name], console)

        # No name → multiselect from the cached PG databases.
        names = sorted(self.Helpers.get_all_db_names())
        if not names:
            console.print("[muted]No databases to drop.[/]")
            return False

        selected = self.prompter.prompt_checkbox(names, "Select databases to drop")
        if not selected:
            console.print("[muted]Aborted.[/]")
            return False
        return self._drop(selected, console)

    def _drop(self, names: list[str], console) -> bool:
        """Confirm once (unless -y), then drop each — reporting per database."""
        if not self.args.yes:
            target = f"'{names[0]}'" if len(names) == 1 else f"{len(names)} databases"
            if not self.prompter.prompt_confirm(
                f"Drop {target}? This destroys real data and cannot be undone."
            ):
                console.print("[muted]Aborted.[/]")
                return False

        failed = []
        for name in names:
            try:
                call("database.drop", name=name)
                console.print(f"[success]✓ Dropped database '{name}'[/]")
            except Exception as e:
                console.print(f"[error]Couldn't drop '{name}':[/] {e}")
                failed.append(name)
        return not failed
