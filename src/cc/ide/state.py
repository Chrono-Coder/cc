"""Stable state contract passed to IDE writers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CcState:
    """Snapshot of cc's active state, projected to IDE writers.

    This is the stable contract for plugins — fields here may only be added,
    never removed or renamed, across minor versions. Writers consume what they
    need and ignore the rest.

    Empty strings ("") indicate the value is unset. Writers should treat empty
    fields as "do not write this key" rather than writing the empty string.
    """

    # Workspace root — where the IDE's config dir (.vscode/, .idea/, ...) lives.
    workspace_path: str

    # Active environment identity.
    env_name: str
    project_name: str
    version_name: str
    branch: str

    # Runtime values referenced by IDE configurations.
    db: str
    odoo_bin: str
    port: str
    addons_path: str
    modules: str
    upgrade_path: str
    python_path: str

    # Filesystem path to the active project — surfaced to extensions that need
    # to locate the project dir within a multi-project workspace (e.g. a VSCode
    # extension that reveals the active project in the file explorer).
    project_path: str = ""
