import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor

from cc.base.command import Command
from cc.utils.ui import Spinner

log = logging.getLogger("CC")


class FetchCommand(Command):
    group = "git"
    name = "fetch"
    description = "Fetch the latest changes for the active version's Odoo repos (or --all)."

    def arguments(self):
        arguments = [
            self.Argument(["-a", "--all"], help="Fetch all git versions", action="store_true"),
        ]
        return arguments

    def _fetch_repo(self, repo_path: str, repo_name: str, pull: bool) -> tuple[bool, str]:
        """Fetch one repo. With pull=True also restore + pull -f (source checkouts);
        with pull=False, fetch only (R&D — never touch the working tree).

        Pure work, no console output, so it's safe to run in a thread pool.
        Returns (ok, detail) for the caller to render serially.
        """
        if not os.path.isdir(repo_path):
            return False, "directory not found"
        if not self.Helpers.git_is_repo(repo_path):
            return False, "not a git repository"

        try:
            fetch = subprocess.run(
                ["git", "fetch", "origin"], cwd=repo_path, capture_output=True, text=True, check=False
            )
            if fetch.returncode != 0:
                return False, fetch.stderr.strip() or "git fetch failed"

            if not pull:
                return True, "fetched"

            restore = subprocess.run(
                ["git", "restore", "."], cwd=repo_path, capture_output=True, text=True, check=False
            )
            if restore.returncode != 0:
                return False, restore.stderr.strip() or "git restore failed"

            branch_proc = subprocess.run(
                ["git", "branch", "--show-current"], cwd=repo_path, capture_output=True, text=True
            )
            current_branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else "HEAD"
            pull_proc = subprocess.run(
                ["git", "pull", "-f", "origin", current_branch],
                cwd=repo_path, capture_output=True, text=True, check=False,
            )
            is_up_to_date = "Already up to date." in (pull_proc.stdout + pull_proc.stderr)
            if pull_proc.returncode != 0 and not is_up_to_date:
                return False, pull_proc.stderr.strip() or "git pull failed"
            return True, "up to date" if is_up_to_date else "updated"
        except FileNotFoundError:
            return False, "git not found in PATH"
        except Exception as e:  # noqa: BLE001 — surface as a per-repo failure, never crash the sweep
            log.debug(f"Unexpected error fetching {repo_path}: {e}", exc_info=True)
            return False, str(e)

    def execute(self):
        log.debug(f"Executing fetch command with args: {self.args}")
        return self._execute_multi_dir()

    def _execute_multi_dir(self):
        odoo_repo = self.Constants.ODOO_ODOO
        enterprise_repo = self.Constants.ODOO_ENTERPRISE
        themes_repo = self.Constants.ODOO_DESIGN_THEMES

        if not self.args.all:
            version = self.active_version
            if not version:
                log.error("No active version found to fetch. Activate a project or use --all.")
                return False
            chosen_versions = [version]
        else:
            log.debug("Fetching all configured versions.")
            chosen_versions = self.version.search([])
            if not chosen_versions:
                log.warning("No versions found in configuration to fetch.")
                return True

        from cc.utils.console import get_console
        console = get_console()
        overall_success = True
        for version in chosen_versions:
            path = version.path
            if not path:
                log.warning(f"Skipping version '{version.name}': No path is configured.")
                continue

            # R&D workspaces hold uncommitted work — fetch-only there (never
            # restore + pull -f, which would discard it). Source checkouts are
            # never hand-edited, so restore + pull keeps them pristine and current.
            # (Founder: "cc git fetch is for source; only R&D writes code.")
            pull = not self._version_is_rnd(version)
            mode = "fetch + pull" if pull else "fetch-only"
            console.print(f"\n[heading]Fetching {version.name}[/]  [muted]{path} · {mode}[/]")

            repos = [
                (f"{path}/{odoo_repo}", f"Odoo ({version.name})"),
                (f"{path}/{enterprise_repo}", f"Enterprise ({version.name})"),
                (f"{path}/{themes_repo}", f"Design Themes ({version.name})"),
            ]

            # Fetch the repos concurrently (network-bound), but render results
            # serially afterwards — the Spinner/Rich console isn't thread-safe.
            with Spinner(
                text=f"Fetching {version.name} ({len(repos)} repos)",
                success_text=None,
                fail_text="",
                debug_mode=self.args.debug,
            ):
                with ThreadPoolExecutor(max_workers=len(repos)) as pool:
                    results = list(
                        pool.map(lambda r: (r[1], *self._fetch_repo(r[0], r[1], pull)), repos)
                    )

            for name, ok, detail in results:
                if ok:
                    console.print(f"  [success]✓[/] {name}  [muted]{detail}[/]")
                else:
                    console.print(f"  [error]✗[/] {name}  [muted]{detail}[/]")
                    overall_success = False
        return overall_success

    def _version_is_rnd(self, version) -> bool:
        """Whether this version's workspace is an R&D (multi-repo dev) checkout."""
        from cc.base.arm.workspace import Workspace
        ws = Workspace.search([("version_id", "=", version.id)], limit=1)
        return bool(ws and ws.is_rnd)
