"""
Odoo version discovery + workspace registration.

Walks the filesystem looking for Odoo installs (directories with
odoo-bin), prompts the user to register each as a Version, then
auto-creates a Workspace for any Version that doesn't have one.

Used by:
  - `cc setup` (the first-time wizard)
  - `cc config` (current entry point, until cc setup ships)
  - `cc workspace add` (when initiated against a fresh path)
"""
import logging
import os
import re

from cc.base.arm.version import Version
from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.constants import Constants
from cc.utils.helpers import Helpers

log = logging.getLogger("CC")


# ── Discovery ─────────────────────────────────────────────────────────


def discover_odoo_installs(scan_root: str) -> list[str]:
    """Walk `scan_root` and return absolute paths of Odoo install
    directories (the parent that contains an 'odoo' subdir with odoo-bin)."""
    # "custom" is pruned for speed: in the conventional Odoo layout it holds
    # client repos (which never contain odoo-bin) and can be huge.
    _BANNED = {
        "Trash", ".Trash", "custom", "node_modules", ".venv", "venv",
        "__pycache__", ".git", "Library", "Applications", ".cache",
    }
    paths = []
    for found in Helpers.search_subdir_file(
        scan_root,
        Constants.ODOO_ODOOBIN,
        True,
        max_depth=4,
        banned_dirs=_BANNED,
        n=20,
    ):
        candidate = os.path.abspath(found)
        # Walk up from odoo-bin to find the version root.
        # odoo-bin can be at: version/odoo-bin, version/odoo/odoo-bin,
        # or version/src/odoo/odoo-bin. The version root contains an
        # 'odoo' or 'enterprise' subdir but is NOT the odoo core itself
        # (the core also has an 'odoo' subdir — the Python package).
        for _ in range(3):
            parent = os.path.dirname(candidate)
            if parent == candidate:
                break
            candidate = parent
            has_odoo_dir = os.path.isdir(os.path.join(candidate, "odoo"))
            has_enterprise = os.path.isdir(os.path.join(candidate, "enterprise"))
            is_odoo_core = os.path.isfile(os.path.join(candidate, "odoo-bin"))
            if (has_odoo_dir or has_enterprise) and not is_odoo_core:
                if candidate not in paths:
                    paths.append(candidate)
                break
    return paths


def derive_version_name(path: str) -> str:
    """Extract a version name from the directory basename."""
    return os.path.basename(path)


def _git_branch(repo_path: str) -> str | None:
    """Read the current branch of a git repo. Works for clones and worktrees."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "branch", "--show-current"],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() or None
    except Exception:
        return None


# ── Multi-dir registration flow ───────────────────────────────────────


def register_versions_multi_dir(prompter, scan_root: str) -> bool:
    """Discover Odoo installs under `scan_root`, prompt to register each.

    Returns True if at least one was registered; False otherwise.
    Triggers ensure_workspaces() at the end.
    """
    console = get_console()
    console.print()
    console.print("[heading]Odoo Versions[/]")
    console.print(f"[primary]{'─' * 40}[/]")
    log.info("Scanning for Odoo installations...")

    found = False
    for path in discover_odoo_installs(scan_root):
        branch = _git_branch(os.path.join(path, "odoo"))
        # Match an existing version by PATH first: the same install may already be
        # registered under a different name (an older naming scheme, or synced from
        # another device). Reusing that name lets version.upsert update in place
        # instead of minting a duplicate row for the same directory.
        existing = Version.find_by(path=path, limit=1)
        name = existing.name if existing else derive_version_name(path)
        default = bool(existing)
        branch_info = f" (branch: {branch})" if branch else ""
        console.print(f"  [muted]{path}{branch_info}[/]")
        if not prompter.prompt_confirm(f"Register {name}?", default=default):
            continue
        call("version.upsert", name=name, path=path, branch=branch or "")
        console.print(f"  ✓ [bold]{name}[/]")
        found = True

    if not found:
        log.warning("No Odoo versions found automatically. Use 'cc workspace add' to add one.")

    ensure_workspaces()
    return found


# ── Workspace bootstrap ───────────────────────────────────────────────


def ensure_workspaces() -> list[str]:
    """For each Version without a Workspace, auto-create one.

    Returns the list of newly created workspace names. No-op if a
    daemon restart is required and fails (logs at debug).
    """
    versions = Version.find_by()
    if not versions:
        return []

    try:
        workspaces = call("workspace.get_all")
    except Exception:
        # Stale daemon without workspace namespace — restart and retry once.
        import subprocess
        import sys
        cc_bin = os.path.join(os.path.dirname(sys.executable), "_cc_internal")
        subprocess.run([cc_bin, "daemon", "restart", "--quiet"], capture_output=True)
        try:
            workspaces = call("workspace.get_all")
        except Exception:
            log.debug("Workspace service unavailable — skipping.")
            return []

    existing_version_ids = {w["version_id"] for w in workspaces if w.get("version_id")}
    existing_names = {w["name"] for w in workspaces}
    created: list[str] = []
    for v in versions:
        if v.id in existing_version_ids:
            continue
        # Only bootstrap versions that live on THIS machine. A synced multi-device
        # DB also holds the other device's versions (whose paths don't exist here);
        # creating workspaces for those is wrong and can collide on workspace.name.
        if not (v.path and os.path.isdir(v.path)):
            continue
        # workspace.name is unique — skip if a workspace already claims this name
        # (e.g. a synced row whose name matches a local version).
        if v.name in existing_names:
            continue
        call("workspace.create", name=v.name, path=v.path or "", version_id=v.id)
        existing_names.add(v.name)
        created.append(v.name)

    if created:
        console = get_console()
        console.print()
        console.print("[heading]Workspaces[/]")
        console.print(f"[primary]{'─' * 40}[/]")
        for name in created:
            console.print(f"  ✓ Created workspace '[bold]{name}[/]'")

    # IDE templates only for paths that exist locally — never the other device's rows.
    all_paths = set()
    for v in versions:
        if v.path and os.path.isdir(v.path):
            all_paths.add(v.path)
    for w in workspaces:
        if w.get("path") and os.path.isdir(w["path"]):
            all_paths.add(w["path"])
    _ensure_ide_templates(all_paths)

    return created


def _ensure_ide_templates(workspace_paths: set[str]) -> None:
    from pathlib import Path
    from cc.ide import active_writers

    for ws_path in workspace_paths:
        p = Path(ws_path)
        launch = p / ".vscode" / "launch.json"
        if launch.exists():
            continue
        for writer in active_writers(p):
            try:
                writer.setup(p)
                log.info(f"Wrote {writer.name} debug templates → {p}")
            except Exception as e:
                log.debug(f"[registration] {writer.name} setup failed for {p}: {e}")
