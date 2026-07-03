"""
pyenv virtualenv linking for Odoo versions.

Owns the logic to link an existing pyenv virtualenv to a Version,
create a new one from a Python base, and (optionally) pip-install the
matching odoo/requirements.txt into it.

Used by:
  - `cc setup` / `cc config` wizard (auto-link flow during version setup)
  - `cc config --set-pyenv NAME` interactive picker
  - `cc config venv link` (the new standalone link command)
"""
import logging
import os
import subprocess

from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.helpers import Helpers

log = logging.getLogger("CC")


def _venv_name_for(version_name: str) -> str:
    """Default virtualenv name for a version (`cc-vXX`)."""
    return f"cc-{version_name.lower().replace(' ', '-')}"


def install_requirements(version, venv_name: str, prompter) -> bool:
    """Offer to install Odoo's requirements.txt into the virtualenv.

    Returns True on success, False otherwise (including user decline).
    """
    req_path = os.path.join(version.path, "odoo", "requirements.txt")
    if not os.path.exists(req_path):
        log.debug(f"No requirements.txt found at {req_path}, skipping.")
        return False
    if not prompter.prompt_confirm(
        f"  Install Odoo requirements into '{venv_name}'? (pip install -r odoo/requirements.txt)"
    ):
        return False
    pip = Helpers.pyenv_get_python_path(venv_name).replace("/python", "/pip")
    log.info("  Installing requirements, this may take a minute...")
    try:
        subprocess.run([pip, "install", "-r", req_path], check=True)
        log.info(f"  ✓ Requirements installed into '{venv_name}'.")
        return True
    except subprocess.CalledProcessError as e:
        log.error(f"  Failed to install requirements: {e}")
        return False


def auto_link_version(version, prompter) -> bool:
    """Wizard-flow: for one version, link/create a pyenv venv with
    sensible defaults. Three branches in priority order:
      1. existing `cc-vXX` virtualenv → confirm link
      2. .python-version file detected → confirm create from that base
      3. manual base-version pick from `pyenv versions`

    Returns True if a venv was linked, False if user skipped or pyenv
    isn't usable for this path.
    """
    console = get_console()
    current = version.pyenv_virtualenv
    if current and current != "skip":
        console.print(
            f"  [bold]{version.name:<10}[/] "
            f"[muted]already linked →[/] [primary]{current}[/]"
        )
        return False

    venv_name = _venv_name_for(version.name)

    # 1. Existing cc-vXX virtualenv?
    if Helpers.pyenv_virtualenv_exists(venv_name):
        if not prompter.prompt_confirm(
            f"  Link {version.name} to existing virtualenv '{venv_name}'?"
        ):
            return False
        _save_link(version, venv_name)
        console.print(f"  ✓ {version.name} → {venv_name}")
        console.print(f"  [muted]To delete this virtualenv: pyenv virtualenv-delete {venv_name}[/]")
        install_requirements(version, venv_name, prompter)
        return True

    # 2. .python-version detected at the version's path?
    detected = Helpers.pyenv_detect_version_from_path(version.path)
    if detected:
        if not prompter.prompt_confirm(
            f"  Create pyenv virtualenv '{venv_name}' from Python {detected} for {version.name}?"
        ):
            return False
        if not Helpers.pyenv_create_virtualenv(detected, venv_name):
            return False
        _save_link(version, venv_name)
        console.print(f"  ✓ {version.name} → {venv_name}")
        console.print(f"  [muted]To delete: pyenv virtualenv-delete {venv_name}[/]")
        install_requirements(version, venv_name, prompter)
        return True

    # 3. Manual base-version pick
    available = Helpers.pyenv_list_versions()
    if not available:
        return False
    if not prompter.prompt_confirm(f"  Set up a Python environment for {version.name}?"):
        return False
    base = prompter.prompt_autocomplete(available, f"Choose Python version for {version.name}")
    if not base:
        return False
    if not Helpers.pyenv_create_virtualenv(base, venv_name):
        return False
    _save_link(version, venv_name)
    console.print(f"  ✓ {version.name} → {venv_name}")
    console.print(f"  [muted]To delete this virtualenv: pyenv virtualenv-delete {venv_name}[/]")
    install_requirements(version, venv_name, prompter)
    return True


def interactive_link(version_name: str, prompter) -> bool:
    """User-driven linker: pick from all existing pyenv virtualenvs
    (or create a new one). Used by `cc config --set-pyenv NAME` and
    `cc config venv link`.
    """
    from cc.base.arm.version import Version

    version = Version.find_by(name=version_name, limit=1)
    if not version:
        log.error(f"Version '{version_name}' not found. Run 'cc config -l' to see configured versions.")
        return False

    if not Helpers.pyenv_is_installed():
        log.error("pyenv is not installed.")
        return False

    CREATE_NEW = "+ Create new virtualenv"
    current = version.pyenv_virtualenv
    all_venvs = [CREATE_NEW] + Helpers.pyenv_list_all_virtualenvs()

    chosen = prompter.prompt_autocomplete(
        all_venvs,
        f"Choose pyenv virtualenv for {version_name}"
        + (f" (current: {current})" if current else ""),
    )
    if not chosen:
        return False

    if chosen == CREATE_NEW:
        base_versions = Helpers.pyenv_list_versions()
        if not base_versions:
            log.error("No pyenv Python versions installed.")
            return False
        base = prompter.prompt_autocomplete(base_versions, "Choose base Python version")
        if not base:
            return False
        default_name = _venv_name_for(version_name)
        venv_name = prompter.prompt_input_single("Virtualenv name", default=default_name)
        if not venv_name:
            return False
        if not Helpers.pyenv_create_virtualenv(base, venv_name):
            return False
        install_requirements(version, venv_name, prompter)
        chosen = venv_name

    _save_link(version, chosen)
    log.info(f"Linked {version_name} → {chosen}")
    get_console().print(f"  [muted]To delete this virtualenv: pyenv virtualenv-delete {chosen}[/]")
    return True


def _save_link(version, venv_name: str) -> None:
    """Persist the version → virtualenv link via the daemon."""
    call("version.update", version_id=version.id, pyenv_virtualenv=venv_name)
