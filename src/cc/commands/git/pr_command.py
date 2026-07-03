import json
import logging
import subprocess
import webbrowser

from cc.base.command import Command
from cc.utils.gh import (
    GhError,
    gh_available,
    gh_pr_checkout,
    gh_pr_list,
    gh_pr_merge,
    gh_pr_view,
    gh_search_prs,
    gh_username,
)

log = logging.getLogger("CC")


class PrCommand(Command):
    group = "git"
    name = "pr"
    description = "GitHub pull request workflow — list, create, view, merge, checkout, checks."

    def arguments(self):
        return [
            self.Argument(
                ["action"],
                nargs="?",
                type=str,
                choices=["list", "create", "view", "merge", "checkout", "checks"],
                help="PR action (default: interactive list).",
            ),
            self.Argument(
                ["target"],
                nargs="?",
                type=str,
                help="PR number or base branch (for create).",
            ),
            self.Argument(["--json"], action="store_true", help="Output as JSON."),
        ]

    def execute(self):
        log.debug(f"Executing pr command with args: {self.args}")

        if not gh_available():
            from cc.utils.console import get_console
            get_console().print("[error]gh CLI not found.[/] Install from [primary]https://cli.github.com/[/]")
            return False

        action = self.args.action
        if action == "create":
            return self._create_pr()
        if action == "view":
            return self._view_pr()
        if action == "merge":
            return self._merge_pr()
        if action == "checkout":
            return self._checkout_pr()
        if action == "checks":
            return self._checks_pr()
        return self._list_prs()

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def _list_prs(self) -> bool:
        from cc.utils.console import get_console
        console = get_console()

        username = gh_username()
        if not username:
            console.print("[error]Not authenticated.[/] Run [primary]gh auth login[/] first.")
            return False

        try:
            prs = gh_search_prs(author="@me")
        except GhError as e:
            log.error(f"Failed to fetch PRs: {e}")
            return False

        if not prs:
            console.print("[muted]No open pull requests found.[/]")
            return True

        if self.args.json:
            out = [
                {
                    "number": pr["number"],
                    "title": pr["title"],
                    "repo": pr["repository"]["nameWithOwner"],
                    "url": pr["url"],
                    "updated_at": pr["updatedAt"],
                }
                for pr in prs
            ]
            print(json.dumps(out, indent=2))
            return True

        pr, action = self._pick_pr(prs)
        if not pr:
            return True

        number = pr.get("number")
        repo = pr.get("repository", {}).get("nameWithOwner")

        if action == "checkout":
            try:
                gh_pr_checkout(number)
                console.print(f"[success]✓ Checked out PR #{number}.[/]")
                return True
            except GhError as e:
                log.error(f"Failed to checkout PR #{number}: {e}")
                return False

        if action == "merge":
            if not repo:
                console.print("[error]Could not determine the PR's repository.[/]")
                return False
            return self._do_merge(repo, number)

        # default: open in browser
        url = pr["url"]
        console.print(f"[muted]Opening: {url}[/]")
        webbrowser.open(url)
        return True

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    def _create_pr(self) -> bool:
        from cc.utils.console import get_console
        console = get_console()

        from_branch = self.Helpers.git_get_branch_name()
        if not from_branch:
            console.print("[error]Not on a git branch.[/]")
            return False

        owner_repo = self._get_owner_repo()
        if not owner_repo:
            return False

        # Default base = the active version's branch (e.g. 18.0), not always main —
        # Odoo PRs target the version line, not main. Explicit `cc git pr create <base>`
        # still overrides.
        version = self.active_version
        default_base = version.branch if version and version.branch else "main"
        base = self.args.target or default_base
        url = f"https://github.com/{owner_repo}/compare/{base}...{from_branch}"
        console.print(f"[muted]Opening: {url}[/]")
        webbrowser.open(url)
        return True

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    def _view_pr(self) -> bool:
        from cc.utils.console import get_console
        console = get_console()

        owner_repo = self._get_owner_repo()
        if not owner_repo:
            return False

        number = self._resolve_pr_number()
        if not number:
            return False

        try:
            pr = gh_pr_view(owner_repo, number)
        except GhError as e:
            log.error(f"Failed to view PR: {e}")
            return False

        from cc.utils.panels import themed_table
        table = themed_table(title=f"PR #{pr['number']}")
        table.add_column("Field", style="muted")
        table.add_column("Value")

        state = pr["state"]
        review = pr.get("reviewDecision") or "—"
        draft = " (draft)" if pr.get("isDraft") else ""

        table.add_row("Title", pr["title"])
        table.add_row("State", f"{state}{draft}")
        table.add_row("Review", review)
        table.add_row("Branch", f"{pr['headRefName']} → {pr['baseRefName']}")
        table.add_row("Author", pr["author"].get("login", "?"))
        table.add_row("Changes", f"+{pr.get('additions', 0)} −{pr.get('deletions', 0)} ({pr.get('changedFiles', 0)} files)")
        table.add_row("URL", pr["url"])
        console.print(table)
        return True

    # ------------------------------------------------------------------
    # Merge
    # ------------------------------------------------------------------

    def _merge_pr(self) -> bool:
        owner_repo = self._get_owner_repo()
        if not owner_repo:
            return False
        number = self._resolve_pr_number()
        if not number:
            return False
        return self._do_merge(owner_repo, number)

    def _do_merge(self, owner_repo: str, number: int) -> bool:
        from cc.utils.console import get_console
        console = get_console()
        method = self.prompter.prompt_autocomplete(
            options=["squash", "merge", "rebase"],
            label="Merge method",
        )
        if not method:
            return True
        try:
            gh_pr_merge(owner_repo, number, method=method)
            console.print(f"[success]✓ PR #{number} merged via {method}.[/]")
            return True
        except GhError as e:
            log.error(f"Failed to merge PR: {e}")
            return False

    # ------------------------------------------------------------------
    # Checkout
    # ------------------------------------------------------------------

    def _checkout_pr(self) -> bool:
        from cc.utils.console import get_console
        console = get_console()

        number = self._resolve_pr_number()
        if not number:
            return False

        try:
            gh_pr_checkout(number)
            console.print(f"[success]✓ Checked out PR #{number}.[/]")
            return True
        except GhError as e:
            log.error(f"Failed to checkout PR: {e}")
            return False

    # ------------------------------------------------------------------
    # Checks
    # ------------------------------------------------------------------

    def _checks_pr(self) -> bool:
        from cc.utils.console import get_console
        from cc.utils.gh import gh_commit_status
        console = get_console()

        owner_repo = self._get_owner_repo()
        if not owner_repo:
            return False

        number = self._resolve_pr_number()
        if not number:
            return False

        try:
            pr = gh_pr_view(owner_repo, number)
        except GhError as e:
            log.error(f"Failed to fetch PR: {e}")
            return False

        try:
            status = gh_commit_status(owner_repo, pr["headRefName"])
        except GhError:
            status = {"statuses": []}

        statuses = status.get("statuses", [])
        if not statuses:
            console.print(f"[muted]No checks reported for PR #{number}.[/]")
            return True

        from cc.utils.panels import themed_table
        table = themed_table(title=f"Checks — PR #{number}")
        table.add_column("Context")
        table.add_column("State")
        table.add_column("Description")

        state_styles = {"success": "success", "pending": "warning", "failure": "error", "error": "error"}
        for s in statuses:
            state = s.get("state", "?")
            style = state_styles.get(state, "")
            table.add_row(
                s.get("context", "?"),
                f"[{style}]{state}[/]" if style else state,
                s.get("description", "") or "",
            )

        console.print(table)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_owner_repo(self) -> str | None:
        url = subprocess.run(
            ["git", "config", "--get", "remote.origin.url"],
            capture_output=True, text=True,
        ).stdout.strip()
        owner_repo = self.Helpers.parse_github_remote(url)
        if not owner_repo:
            from cc.utils.console import get_console
            get_console().print(f"[error]Could not parse GitHub remote:[/] {url}")
        return owner_repo

    def _resolve_pr_number(self) -> int | None:
        from cc.utils.console import get_console
        target = self.args.target
        if target:
            try:
                return int(target)
            except ValueError:
                get_console().print(f"[error]Invalid PR number:[/] {target}")
                return None

        # No number given → resolve the open PR for the current branch.
        branch = self.Helpers.git_get_branch_name()
        owner_repo = self._get_owner_repo()
        if branch and owner_repo:
            try:
                prs = gh_pr_list(owner_repo, head=branch)
            except GhError as e:
                log.debug(f"gh pr list failed: {e}")
                prs = []
            if prs:
                return prs[0]["number"]
            get_console().print(
                f"[error]No open PR for branch[/] [branch]{branch}[/][error].[/] "
                f"Pass a number: [primary]cc git pr view <number>[/]"
            )
            return None

        get_console().print("[error]PR number required.[/] Usage: [primary]cc git pr view <number>[/]")
        return None

    def _pick_pr(self, prs: list) -> tuple:
        import sys

        from prompt_toolkit.application import Application
        from prompt_toolkit.cursor_shapes import CursorShape
        from prompt_toolkit.formatted_text import FormattedText
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import HSplit, Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.widgets import Frame

        from cc.utils.prompter.prompter import PROMPTER_STYLE

        cursor = [0]
        state = {"pr": None, "action": "open"}

        def _rows() -> FormattedText:
            parts = []
            for i, pr in enumerate(prs):
                is_sel = i == cursor[0]
                bar = ("class:pointer", " ▌ ") if is_sel else ("class:col.label", " │ ")
                repo = pr.get("repository", {}).get("nameWithOwner", "?")
                title = pr.get("title", "")
                num = pr.get("number", "")
                line = f"#{num}  {repo}  {title}"
                try:
                    import shutil
                    w = shutil.get_terminal_size().columns - 6
                    if len(line) > w:
                        line = line[:w - 1] + "…"
                except Exception:
                    pass
                name_style = "class:col.main" if is_sel else ""
                parts += [bar, (name_style, line), ("", "\n")]
            return FormattedText(parts)

        def _footer() -> FormattedText:
            return FormattedText([
                ("class:col.label", " ↑↓"), ("", " nav"),
                ("class:col.label", "  ↵/o"), ("", " open"),
                ("class:col.label", "  c"), ("", " checkout"),
                ("class:col.label", "  m"), ("", " merge"),
                ("class:col.label", "  esc"), ("", " cancel"),
            ])

        layout = Layout(
            HSplit([
                Frame(
                    Window(
                        FormattedTextControl(_rows),
                        height=min(len(prs), 16),
                    ),
                    title=" Open Pull Requests ",
                ),
                Window(FormattedTextControl(_footer), height=1),
            ])
        )

        kb = KeyBindings()

        @kb.add("up")
        def _up(event):
            if cursor[0] > 0:
                cursor[0] -= 1

        @kb.add("down")
        def _down(event):
            if cursor[0] < len(prs) - 1:
                cursor[0] += 1

        def _choose(action):
            def _handler(event):
                state["pr"] = prs[cursor[0]]
                state["action"] = action
                event.app.exit()
            return _handler

        kb.add("enter")(_choose("open"))
        kb.add("o")(_choose("open"))
        kb.add("c")(_choose("checkout"))
        kb.add("m")(_choose("merge"))

        @kb.add("escape")
        @kb.add("c-c")
        def _cancel(event):
            event.app.exit()

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=PROMPTER_STYLE,
            full_screen=False,
            cursor=CursorShape._NEVER_CHANGE,
        )

        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
        app.output.show_cursor = lambda: None
        app.run()
        sys.stdout.write("\x1b[?25h")
        sys.stdout.flush()

        return state["pr"], state["action"]
