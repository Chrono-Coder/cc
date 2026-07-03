import logging
from datetime import datetime, timezone

from rich.panel import Panel
from rich.text import Text

from cc.utils.console import get_console
from cc.utils.panels import env_card

from .project_command import ProjectCommand

log = logging.getLogger("CC")


def _time_ago(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso).astimezone(timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
        if secs < 60:
            return "now"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return ""


class StatusCommand(ProjectCommand):
    name = "stat"
    description = "Show the active environment (project, version, branch, database)."

    def arguments(self):
        # Deliberately NOT super().arguments(): stat inherits ProjectCommand
        # for its helpers, not its CLI surface — the create/delete args would
        # pollute `cc stat -h` with actions stat doesn't perform.
        return [
            self.Argument(
                names=["-v", "--verbose"],
                action="store_true",
                help="List all environments for the active project.",
            ),
            self.Argument(
                names=["-s", "--short"],
                action="store_true",
                help="Compact one-line output per active environment.",
            ),
            self.Argument(
                names=["--json"],
                action="store_true",
                help="Output as JSON.",
            ),
        ]

    def execute(self):
        import json

        from cc.daemon.client import call

        try:
            data = call("env.get_status", version_id=self._version_id(), verbose=bool(self.args.verbose))
        except Exception as e:
            log.error(f"Failed to get status: {e}")
            return False

        if self.args.json:
            print(json.dumps(data, indent=2))
            return True

        console = get_console()

        if self.args.short:
            for env in data["environments"]:
                console.print(self._short_panel(env, data))
            return True

        if not data["environments"]:
            console.print("[warning]⚠ No environments found.[/] Create one with [primary]cc switch PROJECT[/]")
            return True

        if data["project"]:
            console.print(f"\nEnvironments for '[primary]{data['project']}[/]':")

        for env in data["environments"]:
            console.print(env_card(env))
        return True

    def _short_panel(self, env, data) -> Panel:
        project = env.get("project_name") or data.get("project") or ""
        name = env["name"]
        title = f"{project} / {name}" if project else name

        version = env.get("version") or ""
        database = env.get("database") or ""
        branch = env.get("branch_name") or ""
        ago = _time_ago(env["last_used_at"]) if env.get("last_used_at") else ""

        detail = Text()
        sep = "   "
        if version:
            detail.append(version, style="primary")
            detail.append(sep)
        if database:
            detail.append(database)
            detail.append(sep)
        if branch:
            detail.append(branch, style="branch")
            detail.append(sep)
        if ago:
            detail.append(ago, style="muted")

        return Panel(
            detail,
            title=title,
            title_align="left",
            border_style="primary",
            padding=(0, 1),
            expand=False,
        )

    def _version_id(self):
        try:
            version = self._detect_version_from_cwd()
            return version.id if version else None
        except Exception:
            return None
