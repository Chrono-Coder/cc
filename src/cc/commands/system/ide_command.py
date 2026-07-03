"""``cc config ide`` — manage editor integration writers and one-time setup.

Subcommands:

* ``cc config ide list``  — show all registered IDE writers and which are active
                     for the current workspace.
* ``cc config ide setup`` — invoke ``writer.setup()`` on every active writer for
                     the active version's path. This is the only legitimate
                     way to (re)write IDE template files like
                     ``launch.json``. ``cc switch`` never touches them.
"""

import logging
from pathlib import Path

from cc.base.command import Command
from cc.ide import active_writers, all_writers
from cc.utils.console import get_console

log = logging.getLogger("CC")


class IdeCommand(Command):
    group = "config"
    name = "ide"
    description = "Manage editor integration writers (setup, list)."

    def arguments(self):
        return [
            self.Argument(
                names=["action"],
                type=str,
                nargs="?",
                default="list",
                choices=["list", "setup"],
                help="Action to perform. Defaults to list.",
            ),
            self.Argument(
                names=["--path"],
                type=str,
                default=None,
                help="Override the workspace path (defaults to the active version's path).",
            ),
        ]

    def execute(self):
        action = self.args.action or "list"
        if action == "list":
            return self._list()
        if action == "setup":
            return self._setup()
        return False

    # ── list ─────────────────────────────────────────────────────────────

    def _list(self) -> bool:
        console = get_console()
        workspace = self._resolve_workspace(required=False)
        registered = all_writers()
        active = {w.name for w in active_writers(workspace)} if workspace else set()

        if not registered:
            console.print("[warning]No IDE writers registered.[/]")
            return True

        console.print()
        console.print("[heading]Registered IDE writers[/]")
        for w in registered:
            badge = "[success]●[/] active" if w.name in active else "[muted]○ inactive[/]"
            console.print(f"  [primary]{w.name:<12}[/] {badge}")
        console.print()

        if workspace:
            console.print(f"[muted]workspace:[/] {workspace}")
        else:
            console.print("[muted]No active version — workspace path could not be resolved.[/]")
        console.print()
        return True

    # ── setup ────────────────────────────────────────────────────────────

    def _setup(self) -> bool:
        console = get_console()
        workspace = self._resolve_workspace(required=True)
        if workspace is None:
            return False

        writers = active_writers(workspace)
        if not writers:
            console.print(
                f"[warning]No IDE writers active for {workspace}.[/] "
                "Set [primary]cc.ide[/] to one of: "
                + ", ".join(w.name for w in all_writers())
            )
            return False

        for writer in writers:
            try:
                writer.setup(workspace)
                console.print(
                    f"[success]✓[/] [primary]{writer.name}[/] templates written → {workspace}"
                )
            except Exception as e:
                log.warning(f"IDE writer {writer.name!r} setup() failed: {e}")
                console.print(f"[error]✗[/] [primary]{writer.name}[/] setup failed: {e}")
        return True

    # ── helpers ──────────────────────────────────────────────────────────

    def _resolve_workspace(self, required: bool) -> Path | None:
        if self.args.path:
            return Path(self.args.path).expanduser().resolve()

        version = self.active_version
        if version and version.path:
            return Path(version.path)

        if required:
            console = get_console()
            console.print(
                "[error]No active version with a path.[/] "
                "Switch to an environment first, or pass [primary]--path[/]."
            )
        return None
