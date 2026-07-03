"""CLI event handlers for cc-rnd (the cc.event_handlers entry point).

The switch-rebase, moved off switch_command: on `switch.checkout` (a collecting
hook), check out + rebase the env's branch across the shared Odoo repos and
return the repos where checkout failed, which the switch folds into its failure
summary. Self-gating — a no-op for non-R&D workspaces or a missing env/version,
so it's harmless even though it's only loaded when cc-rnd is installed.
"""
import logging
import os

from cc.events import subscribe
from cc.events.events import SwitchCheckoutEvent

log = logging.getLogger("CC")


@subscribe("switch.checkout")
def checkout_rnd_branches(event: SwitchCheckoutEvent) -> list:
    """For each shared repo (odoo, enterprise, design-themes, upgrade,
    upgrade-util): fetch fork+upstream (unless no_pull), check out <branch>
    wherever it exists (local → fork → upstream), then rebase on
    upstream/<version> (unless no_pull). Returns repos where the branch existed
    but checkout failed (e.g. uncommitted changes) — a missing branch is a skip."""
    from cc.base.arm.environment import Environment
    from cc.base.arm.setting import Setting
    from cc.base.arm.version import Version
    from cc.utils.console import get_console
    from cc.utils.constants import Constants
    from cc.utils.shell import run_command

    opt_out = Setting.find_by(name=Constants.SETTING_RND_AUTO_REBASE, limit=1)
    if opt_out and str(opt_out.value).lower() in ("false", "0", "no"):
        return []
    if not event.env_id or not event.version_id:
        return []
    env = Environment.find_by(id=event.env_id, limit=1)
    if not env or not env.branch_name:
        return []
    project = env.project_id
    if not project or not project.workspace_id or not project.workspace_id.is_rnd:
        return []
    version = Version.find_by(id=event.version_id, limit=1)
    if not version or not version.path or not version.branch:
        return []

    branch = env.branch_name
    no_pull = event.no_pull
    repos = [
        Constants.ODOO_ODOO,
        Constants.ODOO_ENTERPRISE,
        Constants.ODOO_DESIGN_THEMES,
        Constants.ODOO_UPGRADE,
        Constants.ODOO_UPGRADE_UTIL,
    ]
    console = get_console()

    failed: list[str] = []
    for repo in repos:
        repo_path = os.path.join(version.path, repo)
        if not os.path.isdir(repo_path):
            continue

        fork, upstream = _resolve_remotes(repo_path)

        if not no_pull:
            for remote in dict.fromkeys(r for r in (fork, upstream) if r):
                run_command(["git", "-C", repo_path, "fetch", remote], timeout=30)

        if _ref_exists(repo_path, f"refs/heads/{branch}"):
            checkout = ["git", "-C", repo_path, "checkout", branch]
        elif fork and _ref_exists(repo_path, f"refs/remotes/{fork}/{branch}"):
            checkout = ["git", "-C", repo_path, "checkout", "-b", branch, "--track", f"{fork}/{branch}"]
        elif upstream and _ref_exists(repo_path, f"refs/remotes/{upstream}/{branch}"):
            checkout = ["git", "-C", repo_path, "checkout", "-b", branch, "--track", f"{upstream}/{branch}"]
        else:
            console.print(f"  [muted]{repo}: no '{branch}' — left as-is[/]")
            continue

        r = run_command(checkout)
        if r.returncode != 0:
            log.warning(f"  {repo}: checkout '{branch}' failed: {r.stderr.strip()}")
            failed.append(repo)
            continue
        console.print(f"  [muted]{repo}: checked out '{branch}'[/]")

        if not no_pull and upstream:
            upstream_branch = f"{upstream}/{version.branch}"
            rb = run_command(["git", "-C", repo_path, "rebase", upstream_branch])
            if rb.returncode != 0:
                log.warning(f"  {repo}: rebase on {upstream_branch} conflict — aborting")
                run_command(["git", "-C", repo_path, "rebase", "--abort"])

    return failed


def _resolve_remotes(repo_path: str) -> tuple:
    """(fork, upstream) remote names resolved by URL (odoo-dev fork vs canonical
    odoo upstream); either may be None for a fork-less repo like upgrade."""
    from cc.utils.helpers import Helpers
    from cc.utils.shell import run_command

    r = run_command(["git", "-C", repo_path, "remote", "-v"])
    if r.returncode != 0:
        return None, None
    return Helpers.parse_odoo_remotes(r.stdout)


def _ref_exists(repo_path: str, ref: str) -> bool:
    from cc.utils.shell import run_command

    r = run_command(["git", "-C", repo_path, "show-ref", "--verify", "--quiet", ref])
    return r.returncode == 0
