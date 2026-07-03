"""`cc rnd` command group (the cc.commands entry point). Importing this module
registers the R&D commands with cc's command discovery. These were the
`cc workspace create` / `cc workspace consolidate` actions, moved out of core."""
import os

from cc.base.command import Command
from cc.daemon.client import call


class RndCreateCommand(Command):
    group = "rnd"
    name = "create"
    description = "Create an R&D workspace by git-worktreeing a version's repos."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", help="New workspace name"),
        ]

    def execute(self):
        """Create an R&D workspace by git-worktreeing an existing version's repos.

        Shares the source clones' object store — no multi-GB re-clone. Produces a
        new directory of detached worktrees plus its own version + workspace rows.
        """
        from cc.utils.console import get_console

        from cc.rnd import worktree
        console = get_console()
        name = self.args.name

        versions = self.version.search([])
        if not versions:
            console.print("[error]No versions found.[/] Add one first via [primary]cc workspace add[/] or [primary]cc config[/].")
            return False

        src_name = self.prompter.prompt_autocomplete(
            [v.name for v in versions], "Source version (clones to worktree from)"
        )
        if not src_name:
            return False
        source = self.version.find_by(name=src_name, limit=1)
        if not source or not source.path or not os.path.isdir(source.path):
            console.print(f"[error]Version '{src_name}' has no valid path.[/]")
            return False

        repos = [r for r in worktree.REPO_NAMES if worktree.is_git_repo(os.path.join(source.path, r))]
        if not repos:
            console.print(f"[error]No git repos found under {source.path}.[/]")
            return False

        if not name:
            name = self.prompter.prompt_input_single("New workspace name")
        if not name:
            return False

        base_branch = source.branch or self.prompter.prompt_input_single("Base branch", default="master") or "master"
        default_path = os.path.join(os.path.dirname(source.path.rstrip(os.sep)), name)
        # The worktree dir is created here, so it need not exist yet — completion
        # + ~ expansion only, no existence check.
        target = self.prompter.prompt_input_path("New workspace path", default=default_path, kind="dir") or default_path
        if os.path.isdir(target) and os.listdir(target):
            console.print(f"[error]Target '{target}' exists and isn't empty.[/]")
            return False

        console.print(
            f"\n[muted]Worktreeing {len(repos)} repo(s) from {source.path} → {target} (detached @ {base_branch})[/]"
        )
        results = worktree.create_worktrees(source.path, target, base_branch, repo_names=repos)
        created = [r for r in results if r["ok"]]
        for r in results:
            mark = "[success]✓[/]" if r["ok"] else "[error]✗[/]"
            suffix = "" if r["ok"] else f": {r['error']}"
            console.print(f"  {mark} {r['repo']}{suffix}")
        if not created:
            console.print("[error]No worktrees created.[/]")
            return False

        ver = call("version.create", name=name, path=target, branch=base_branch)
        call("workspace.create", name=name, path=target, is_rnd=True, version_id=ver["id"])
        console.print(
            f"\n[success]✓ Workspace '{name}' created[/] "
            f"[muted]({len(created)} repos, sharing {source.name}'s object store).[/]"
        )
        self._maybe_run_ide_setup(ver["id"])
        return True

    def _maybe_run_ide_setup(self, version_id: int) -> None:
        """Offer to write IDE debugger templates for the linked version's path.

        This is the one-shot ``setup()`` half of the IDE writer contract — it
        only ever runs here (or via the explicit ``cc config ide setup`` command).
        ``cc switch`` never touches launch.json.
        """
        if not version_id:
            return
        v = self.version.find_by(id=version_id, limit=1)
        if not v or not v.path:
            return

        from pathlib import Path

        from cc.ide import active_writers
        from cc.utils.console import get_console

        workspace = Path(v.path)
        writers = active_writers(workspace)
        if not writers:
            return

        names = ", ".join(w.name for w in writers)
        if not self.prompter.prompt_confirm(
            f"Write debugger templates now for {names}? (run later with: cc config ide setup)",
            default=True,
        ):
            return

        console = get_console()
        for writer in writers:
            try:
                writer.setup(workspace)
                console.print(f"[success]✓[/] [primary]{writer.name}[/] templates written → {workspace}")
            except Exception as e:
                console.print(f"[error]✗[/] [primary]{writer.name}[/] setup failed: {e}")


class RndConsolidateCommand(Command):
    group = "rnd"
    name = "consolidate"
    description = "Fold duplicate full clones into worktrees of one canonical clone."

    def arguments(self):
        return []

    def execute(self):
        """Fold duplicate full clones of each repo into worktrees of one canonical
        clone, reclaiming the disk wasted by cloning the same repo per version.

        Reversible: each converted clone is moved to '<path>.cc-bak' (instant,
        same-filesystem) and replaced by a worktree; nothing is deleted.
        """
        from cc.utils.console import get_console

        from cc.rnd import worktree
        console = get_console()

        version_paths = [v.path for v in self.version.search([]) if v.path]
        groups = worktree.plan_consolidation(version_paths)
        if not groups:
            console.print("\n[success]Nothing to consolidate[/] — no duplicate full clones found.\n")
            return True

        console.print("\n[heading]Consolidation plan[/]")
        total = 0
        for g in groups:
            console.print(f"\n  [primary]{g['repo']}[/] — canonical: [muted]{g['canonical']['path']}[/]")
            for d in g["dups"]:
                console.print(f"    → convert [muted]{d['path']}[/] (branch {d['branch'] or 'detached'})")
                total += 1
            for info, reason in g["skipped"]:
                console.print(f"    [warning]skip[/] {info['path']} — {reason}")

        if not total:
            console.print("\n[muted]All duplicates were skipped (see reasons above).[/]\n")
            return True

        console.print(
            "\n[muted]Each converted clone is moved to '<path>.cc-bak' (reversible) and replaced by a "
            "worktree. Delete the .cc-bak dirs once verified to reclaim disk.[/]"
        )
        if not self.prompter.prompt_confirm(f"Convert {total} duplicate clone(s) to worktrees?", default=False):
            return False

        backups = []
        for g in groups:
            for d in g["dups"]:
                res = worktree.consolidate_clone(g["canonical"]["path"], d["path"])
                if res["ok"]:
                    console.print(f"  [success]✓[/] {g['repo']}: {d['path']} → worktree")
                    backups.append(res["backup"])
                    for orig, renamed in res.get("preserved", []):
                        console.print(f"      [muted]preserved divergent '{orig}' as '{renamed}'[/]")
                else:
                    console.print(f"  [error]✗[/] {g['repo']}: {d['path']} — {res['error']}")

        if backups:
            console.print(f"\n[success]✓ Consolidated {len(backups)} clone(s).[/]")
            console.print("[muted]Verify, then reclaim disk:[/]")
            for b in backups:
                console.print(f"  [muted]rm -rf {b}[/]")
        return True


def create_port_envs(project, repo_path, fallback_version=None):
    """Discover a ticket's forward-port chain and create one env per
    (version, branch). Returns (created, skipped); existing envs are left
    untouched (idempotent — `cc rnd fw` can re-scan safely). Shared by
    RndProjectCommand and RndFwCommand."""
    from cc.base.arm.version import Version
    from cc.utils.helpers import Helpers

    from cc.rnd import forward_ports
    main = project.main_branch
    if not main:
        return [], []

    branches = Helpers.list_fork_branches(repo_path)
    if main not in branches:
        branches = [main] + branches  # anchor may not be pushed yet
    versions = {v.name: v for v in Version.search([])}
    existing = {e.branch_name for e in project.environment_ids}

    created, skipped = [], []
    for m in forward_ports.match_ports(main, branches, list(versions.keys())):
        if m["branch"] in existing:
            continue
        vname = m["version"]
        ver = versions.get(vname) if vname else None
        if not ver and m["is_anchor"]:
            ver, vname = fallback_version, (fallback_version.name if fallback_version else None)
        if not ver:
            skipped.append(m)
            continue
        call(
            "env.create",
            name=vname,
            project_id=project.id,
            version_name=ver.name,
            version_path=ver.path,
            project_path=ver.path,
            github_url="",
            branch_name=m["branch"],
            database_name=m["branch"],
            module_names=[],
        )
        created.append({"version": vname, "branch": m["branch"]})
    return created, skipped


class RndProjectCommand(Command):
    group = "rnd"
    name = "project"
    description = "Create an R&D project in a worktree workspace (auto-discovers forward-ports)."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", help="Project name"),
            self.Argument(["-w", "--workspace"], type=str, help="R&D workspace (defaults to the one for the cwd)"),
        ]

    def execute(self):
        """Pick home repo + main branch, then auto-discover the forward-port
        chain (one env per <target>-<main>-fw branch on the fork)."""
        from cc.base.arm.workspace import Workspace
        from cc.utils.console import get_console
        console = get_console()

        project_name = self.args.name or self.prompter.prompt_input_single("Project name")
        if not project_name:
            return False

        workspace_name = self.args.workspace
        if not workspace_name:
            detected = self.Helpers.detect_workspace_for_cwd()
            if detected and detected.is_rnd:
                workspace_name = detected.name
        if not workspace_name:
            console.print("[error]No R&D workspace given.[/] Pass [primary]-w <workspace>[/] or run from inside one.")
            return False

        workspace = Workspace.find_by(name=workspace_name, limit=1)
        if not workspace:
            console.print(f"[error]Workspace '{workspace_name}' not found.[/]")
            return False
        if not workspace.is_rnd:
            console.print(f"[error]'{workspace_name}' is not an R&D workspace.[/] Use [primary]cc project create[/].")
            return False
        version = workspace.version_id
        if not version:
            console.print(f"[error]Workspace '{workspace_name}' has no linked version.[/]")
            return False

        candidates = [self.Constants.ODOO_ODOO, self.Constants.ODOO_ENTERPRISE, self.Constants.ODOO_UPGRADE]
        available = [r for r in candidates if os.path.isdir(os.path.join(version.path, r))]
        home_repo = ""
        if available:
            home_repo = self.prompter.prompt_input_multi(available, "Which repo do the module(s) live in?") or ""
        branch_repo = home_repo or self.Constants.ODOO_ODOO
        repo_path = os.path.join(version.path, branch_repo)

        main_branch = ""
        if os.path.isdir(repo_path):
            fork_branches = self.Helpers.list_fork_branches(repo_path)
            if fork_branches:
                main_branch = self.prompter.prompt_autocomplete(
                    fork_branches, f"Main branch ({branch_repo} fork)"
                ) or ""
        if not main_branch:
            main_branch = self.prompter.prompt_input_single("Main branch", default="") or ""
        if not main_branch:
            console.print("[error]A main branch is required for an R&D project.[/]")
            return False

        result = call("project.create", name=project_name, home_repo=home_repo, main_branch=main_branch)
        if not result:
            console.print(f"[error]Failed to create project '{project_name}'.[/]")
            return False
        project = self.project.find_by(id=result["id"], limit=1)
        call("workspace.assign_project", workspace_id=workspace.id, project_id=project.id)

        created, skipped = create_port_envs(project, repo_path, fallback_version=version)

        console.print(
            f"\n[success]✓ Project '{project_name}' created[/] "
            f"[muted](home: {home_repo or branch_repo}, main: {main_branch})[/]"
        )
        for c in created:
            console.print(f"  [success]+[/] env [primary]{c['version']}[/] → {c['branch']}")
        for s in skipped:
            console.print(f"  [warning]skip[/] {s['branch']} — target version not registered in cc")
        if created:
            console.print(f"\nUse [primary]cc switch {project_name}[/] to activate.")
        else:
            console.print(
                f"[warning]No envs created.[/] Register the target versions, then "
                f"[primary]cc rnd fw {project_name}[/]"
            )
        return True


class RndFwCommand(Command):
    group = "rnd"
    name = "fw"
    description = "Scan the fork and add any missing forward-port envs for an R&D project."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, nargs="?", help="R&D project name"),
        ]

    def execute(self):
        from cc.utils.console import get_console
        console = get_console()

        project_alias = self.args.name
        if not project_alias:
            project_alias = self.prompter.prompt_autocomplete(self.project.search([]).mapped("name"), "Choose Project")
            if not project_alias:
                return False

        project = self.project.find_by(name=project_alias, limit=1)
        if not project:
            console.print(f"[error]Project '{project_alias}' not found.[/]")
            return False
        if not project.main_branch:
            console.print(
                f"[error]'{project_alias}' has no main branch[/] — create it with [primary]cc rnd project[/]."
            )
            return False

        workspace = project.workspace_id
        version = workspace.version_id if workspace else None
        if not version or not version.path:
            console.print(f"[error]Project '{project_alias}' has no workspace version path to scan.[/]")
            return False

        repo_path = os.path.join(version.path, project.home_repo or self.Constants.ODOO_ODOO)
        created, skipped = create_port_envs(project, repo_path, fallback_version=version)

        if created:
            for c in created:
                console.print(f"  [success]+[/] env [primary]{c['version']}[/] → {c['branch']}")
            console.print(f"[success]✓ Added {len(created)} forward-port env(s).[/]")
        else:
            console.print("[muted]No new forward-port envs found.[/]")
        for s in skipped:
            console.print(f"  [warning]skip[/] {s['branch']} — target version not registered in cc")
        return True
