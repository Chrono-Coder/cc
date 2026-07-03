"""
`cc intel` — manage the skill telemetry index.

Subcommands:
    cc intel scan [PATH ...]         walk filesystem, register every git repo
    cc intel add-repo PATH [--name]  manual register
    cc intel list-repos              show registered repos with index state
"""
import json
import os

from cc.base.command import Command
from cc.daemon.client import call


class IntelCommand(Command):
    name = "intel"
    description = "Manage skill telemetry — Repository registration + listing."

    def arguments(self):
        return [
            self.Argument(
                names=["action"],
                type=str,
                choices=["scan", "add-repo", "list-repos"],
                help="scan | add-repo | list-repos",
            ),
            self.Argument(
                names=["paths"],
                type=str,
                nargs="*",
                help="For scan: roots to walk. For add-repo: a single path.",
                default=[],
            ),
            self.Argument(
                names=["--name"],
                type=str,
                default=None,
                help="add-repo: override the auto-derived display name",
            ),
            self.Argument(
                names=["--max-depth"],
                type=int,
                default=4,
                help="scan: max directory depth (default 4)",
            ),
            self.Argument(
                names=["--json"],
                action="store_true",
                help="Emit raw JSON",
            ),
        ]

    def execute(self):
        actions = {
            "scan":       self._scan,
            "add-repo":   self._add_repo,
            "list-repos": self._list_repos,
        }
        actions[self.args.action]()

    # ------------------------------------------------------------------ #

    def _scan(self):
        from cc.utils.console import get_console
        roots = [os.path.abspath(p) for p in (self.args.paths or [])] or None
        result = call("intel.scan", roots=roots, max_depth=self.args.max_depth)
        if self.args.json:
            print(json.dumps(result, indent=2))
            return
        console = get_console()
        if not result:
            console.print("[warning]No git repos found.[/]")
            return
        new_count = sum(1 for r in result if not r["already_registered"])
        already = len(result) - new_count
        console.print(f"Scanned: [bold]{len(result)}[/] repos found")
        console.print(f"  · [success]{new_count}[/] newly registered")
        console.print(f"  · [muted]{already}[/] already registered")
        for r in result:
            if r["already_registered"]:
                console.print(f"  [muted]·[/] {r['name']:<30}  [muted]{r['path']}[/]")
            else:
                console.print(f"  [success]+[/] [bold]{r['name']:<30}[/]  [muted]{r['path']}[/]")

    def _add_repo(self):
        from cc.utils.console import get_console
        if not self.args.paths:
            console = get_console()
            console.print("[error]Usage:[/] cc intel add-repo PATH [--name NAME]")
            return False
        path = os.path.abspath(self.args.paths[0])
        result = call("intel.add_repo", path=path, name=self.args.name)
        if self.args.json:
            print(json.dumps(result, indent=2))
            return
        console = get_console()
        console.print(f"[success]Registered:[/] [bold]{result['name']}[/]  [muted]({result['path']})[/]")
        if result["origin_url"]:
            console.print(f"  [muted]origin:[/] {result['origin_url']}")

    def _list_repos(self):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table
        repos = call("intel.list_repos")
        if self.args.json:
            print(json.dumps(repos, indent=2))
            return
        console = get_console()
        if not repos:
            console.print("[warning]No repos registered.[/] Run [primary]cc intel scan[/] or [primary]cc intel add-repo PATH[/].")
            return
        table = themed_table(title="Registered Repos")
        table.add_column("", width=1, justify="center", style="success")
        table.add_column("Name", style="bold")
        table.add_column("Tags", justify="right")
        table.add_column("Symbols", justify="right")
        table.add_column("Path", style="muted", overflow="fold")
        for r in repos:
            indexed = "✓" if r["last_indexed_commit_sha"] else ""
            table.add_row(
                indexed,
                r["name"],
                str(r["skill_tag_count"]),
                str(r["knowledge_count"]),
                r["path"],
            )
        console.print()
        console.print(table)
        console.print()
