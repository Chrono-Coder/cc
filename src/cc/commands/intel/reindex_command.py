"""
`cc reindex` — walk new commits, run the indexer, update skill_tag +
knowledge_index.

  cc reindex                    index every enabled Repository
  cc reindex --repo NAME        index only one
  cc reindex --full             rebuild from scratch (ignore last_indexed_at)
  cc reindex --dump REPO        print raw classifier output for validation
"""
import json

from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.ui import Spinner


class ReindexCommand(Command):
    name = "reindex"
    description = "Rebuild the intel index from git history."

    def arguments(self):
        return [
            self.Argument(
                names=["--repo"],
                type=str,
                default=None,
                help="Limit to one repo (by name or id)",
            ),
            self.Argument(
                names=["--full"],
                action="store_true",
                help="Re-process all commits, ignoring incremental state",
            ),
            self.Argument(
                names=["--dump"],
                type=str,
                default=None,
                help="Print raw SkillTag rows for the given repo (validation)",
            ),
            self.Argument(
                names=["--limit"],
                type=int,
                default=50,
                help="--dump only: how many recent rows to show",
            ),
            self.Argument(
                names=["--json"],
                action="store_true",
                help="Emit raw JSON",
            ),
        ]

    def execute(self):
        from cc.utils.console import get_console
        if self.args.dump:
            self._dump()
            return

        repo_id = self._resolve_repo_id(self.args.repo) if self.args.repo else None
        label = f"Indexing {self.args.repo}…" if self.args.repo else "Indexing all repositories…"
        console = get_console()

        try:
            with Spinner(text=label, success_text="", fail_text="Reindex failed."):
                result = call("intel.reindex", timeout=600, repository_id=repo_id, full=bool(self.args.full))
        except Exception as exc:
            console.print(f"  [error]{exc}[/]", style=None)
            return

        if self.args.json:
            print(json.dumps(result, indent=2))
            return

        if not result:
            console.print("[warning]No repos indexed.[/] Did you run [primary]cc intel scan[/] first?")
            return

        from cc.utils.panels import themed_table
        total_commits = sum(r["commits_processed"] for r in result)
        total_tags = sum(r["skill_tags_added"] for r in result)
        active = [r for r in result if r["commits_processed"] > 0]

        table = themed_table(title="Reindex Results")
        table.add_column("Repository", style="bold")
        table.add_column("Commits", justify="right")
        table.add_column("+Tags", justify="right", style="success")
        table.add_column("Symbols", justify="right")
        table.add_column("Elapsed", justify="right", style="muted")
        table.add_column("Error", style="error", overflow="fold")
        any_row = False
        for r in result:
            if r["commits_processed"] == 0 and not r.get("error"):
                continue
            any_row = True
            table.add_row(
                r["repository_name"],
                str(r["commits_processed"]),
                f"+{r['skill_tags_added']}",
                str(r["knowledge_updated"]),
                f"{r['elapsed_seconds']}s",
                r.get("error") or "",
            )
        console.print()
        if any_row:
            console.print(table)
            console.print()
        console.print(
            f"  [bold]{len(result)}[/] repos scanned, "
            f"[bold]{len(active)}[/] had new commits  "
            f"[muted]([/]{total_commits} commits, [success]+{total_tags}[/] tags[muted])[/]"
        )

    def _dump(self):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table

        repo_id = self._resolve_repo_id(self.args.dump)
        result = call("intel.reindex_dump", repository_id=repo_id, limit=self.args.limit)

        if self.args.json:
            print(json.dumps(result, indent=2))
            return

        console = get_console()
        info = result["repository"]

        # ── Repository summary ────────────────────────────────────────────
        meta = themed_table(title=f"Repository — {info['name']}")
        meta.add_column("Field", style="primary")
        meta.add_column("Value", style="muted", overflow="fold")
        meta.add_row("path", info["path"])
        meta.add_row("origin", info["origin_url"] or "(none)")
        meta.add_row("indexed", info["last_indexed_at"] or "(never)")
        meta.add_row("tags", str(info["skill_tag_count"]))
        meta.add_row("symbols", str(info["knowledge_count"]))
        console.print()
        console.print(meta)

        # ── Tag distribution histogram ────────────────────────────────────
        dist = themed_table(title="Tag distribution")
        dist.add_column("Tag", style="bold")
        dist.add_column("Count", justify="right")
        dist.add_column("", style="primary", overflow="ellipsis", no_wrap=True)
        for tag, count in result["tag_distribution"].items():
            bar = "█" * min(40, count)
            dist.add_row(tag, str(count), bar)
        console.print()
        console.print(dist)

        # ── Recent skill tags ─────────────────────────────────────────────
        recent = themed_table(title="Recent skill tags")
        recent.add_column("When", style="muted")
        recent.add_column("SHA", style="muted")
        recent.add_column("Tag", style="bold")
        recent.add_column("Weight", justify="right")
        recent.add_column("LOC", justify="right")
        for t in result["recent_skill_tags"]:
            recent.add_row(
                t["committed_at"][:19],
                t["commit_sha"],
                t["tag"],
                str(t["weight"]),
                str(t["raw_loc"]),
            )
        console.print()
        console.print(recent)

        # ── Top symbols ───────────────────────────────────────────────────
        top = themed_table(title="Top symbols")
        top.add_column("Symbol", style="bold", overflow="fold")
        top.add_column("Kind", style="primary")
        top.add_column("Commits", justify="right")
        top.add_column("LOC", justify="right")
        for k in result["top_symbols"]:
            top.add_row(k["symbol"], k["kind"], str(k["commit_count"]), str(k["loc"]))
        console.print()
        console.print(top)
        console.print()

    # ------------------------------------------------------------------ #

    def _resolve_repo_id(self, name_or_id) -> int:
        # Resolve a CLI arg (string or int) to a repo id via list_repos
        try:
            return int(name_or_id)
        except (TypeError, ValueError):
            pass
        repos = call("intel.list_repos") or []
        for r in repos:
            if r["name"] == name_or_id:
                return r["id"]
        from cc.utils.console import get_console
        get_console().print(f"[error]No repository named '{name_or_id}'.[/] Try [primary]cc intel list-repos[/].")
        return None
