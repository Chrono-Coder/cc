"""
Interactive cc configuration wizard.

Sequenced walkthrough used by `cc setup` (and currently still by
`cc config` with no args during the transition to the picker-only
surface). Delegates each step to its domain module:

  - settings → cc.config.schema + this module's _configure_setting()
  - versions → cc.workspace.registration
  - pyenv    → cc.venv.linker
  - shell    → cc.shell.installer
  - theme    → cc.theme.picker

Pure module — takes `prompter` as a parameter, no Command-class
dependency.
"""
import logging
import os
from os.path import isdir

from cc.base.arm.setting import Setting
from cc.base.arm.version import Version
from cc.config.schema import settings as _registry
from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.constants import Constants
from cc.utils.helpers import Helpers

log = logging.getLogger("CC")


# ── Auto-detect callbacks (referenced by the schema) ──────────────────


def _detect_download_path() -> str | None:
    path = os.path.join(str(Constants.USER_HOME), "Downloads")
    return path if os.path.isdir(path) else None


_AUTODETECT = {
    "_detect_download_path": _detect_download_path,
}


# ── Per-setting prompt + upsert ───────────────────────────────────────


def _upsert(key: str, value: str) -> None:
    call("setting.upsert", key=key, value=value)


def _configure_setting(sdef: dict, prompter) -> None:
    console = get_console()

    if sdef.get("type") == "section":
        console.print()
        console.print(f"[heading]{sdef['label']}[/]")
        console.print(f"[primary]{'─' * 40}[/]")
        return

    key = sdef["key"]
    label = sdef["label"]
    kind = sdef["type"]
    description = sdef.get("description")

    current = Setting.find_by(name=key, limit=1)
    current_value = current.value if current else None

    auto_detect_name = sdef.get("auto_detect")
    detected = _AUTODETECT[auto_detect_name]() if auto_detect_name else None
    default = current_value or detected

    if description:
        console.print(f"  [muted]{description}[/]")

    if kind == "bool":
        result = prompter.prompt_confirm(label, default=current_value == "true")
        value = "true" if result else "false"

    elif kind == "select":
        options = sdef.get("options", {})
        keys = list(options.keys())
        if current_value:
            current_label = next((k for k, v in options.items() if v == current_value), None)
            if current_label and current_label in keys:
                keys = [current_label] + [k for k in keys if k != current_label]
        result = prompter.prompt_input_multi(keys, label)
        if not result:
            return
        value = options[result]

    elif kind == "path":
        result = prompter.prompt_input_path(label, default=default or "", must_exist=True, kind="dir")
        if not result:
            console.print(f"  [muted]Skipping {label}.[/]")
            return
        value = result

    elif kind == "file":
        result = prompter.prompt_input_path(label, default=default or "", must_exist=True, kind="file")
        if not result:
            return
        value = result

    elif kind == "int":
        fallback = sdef.get("default", "")
        for _ in range(3):
            result = prompter.prompt_input_single(label, default=default or fallback)
            if not result:
                return
            if result.isdigit():
                break
            console.print(f"  [error]'{result}' is not a valid number. Try again.[/]")
        else:
            console.print(f"  [muted]Skipping {label}.[/]")
            return
        value = result

    elif kind == "theme":
        from cc.theme.picker import run_theme_picker
        run_theme_picker()
        return

    else:
        result = prompter.prompt_input_single(label, default=default or "")
        if not result:
            return
        value = result

    _upsert(key, value)
    console.print(f"  ✓ {label} → [primary]{value}[/]")


# ── Version setup ─────────────────────────────────────────────────────


def _configure_versions(prompter) -> None:
    from cc.workspace import registration

    console = get_console()

    default_root = _guess_odoo_root()
    console.print(f"  [muted]Where are your Odoo installations? (e.g. ~/odoo)[/]")
    scan_root = prompter.prompt_input_path(
        "Odoo root directory",
        default=default_root or str(Constants.USER_HOME),
        must_exist=True,
        kind="dir",
    )
    if not scan_root or not isdir(scan_root):
        scan_root = str(Constants.USER_HOME)

    registration.register_versions_multi_dir(prompter, scan_root)


def _guess_odoo_root() -> str | None:
    """Try common Odoo directory locations."""
    home = str(Constants.USER_HOME)
    for candidate in ["odoo", "odoo-dev", "src", "dev", "projects"]:
        path = os.path.join(home, candidate)
        if isdir(path):
            return path
    return None


# ── Python environments (pyenv) ───────────────────────────────────────


def _configure_pyenv(prompter) -> None:
    """Link each registered version to a pyenv virtualenv.

    No-op when pyenv isn't installed. Previously this lived as unreachable
    code after a `return` in _guess_odoo_root and never ran — so `cc setup`
    silently skipped Python environment setup entirely (a day-1 dealbreaker).
    """
    if not Helpers.pyenv_is_installed():
        log.debug("pyenv not installed, skipping Python environment setup.")
        return

    from cc.venv.linker import auto_link_version
    console = get_console()
    console.print()
    console.print("[heading]Python Environments (pyenv)[/]")
    console.print(f"[primary]{'─' * 40}[/]")
    for version in Version.find_by():
        auto_link_version(version, prompter)
    console.print("  [muted]Remember to install Odoo dependencies into each virtualenv:[/]")
    console.print("  [muted]pip install -r odoo/requirements.txt[/]")


# ── Shell integration ─────────────────────────────────────────────────


def _configure_shell_integration(prompter) -> None:
    from cc.shell import installer

    console = get_console()
    console.print()
    console.print("[heading]Shell Integration[/]")
    console.print(f"[primary]{'─' * 40}[/]")

    shell_type = installer.detect_shell()
    if not shell_type:
        shell = os.environ.get("SHELL", "")
        console.print(
            f"  [warning]Shell integration supports zsh, bash, and fish "
            f"(detected: {shell or 'unknown'}).[/]"
        )
        return

    console.print(
        "  [muted]Adds a cc wrapper, daemon auto-start, and prompt segment.[/]"
    )

    if installer.is_installed(shell_type):
        console.print("  [success]✓ Already installed.[/]")
        return

    # Default Yes: without the integration there is no `cc` command at all,
    # only `_cc_internal` - a fresh user who declines ends up stranded.
    if not prompter.prompt_confirm("Install shell integration?", default=True):
        return

    if not installer.install(shell_type):
        return

    if shell_type == "fish":
        console.print(
            "  [success]✓ Installed.[/]"
            " Run [primary]source ~/.config/fish/config.fish[/] to activate."
        )
    elif shell_type == "bash":
        console.print(
            "  [success]✓ Installed.[/]"
            " Run [primary]source ~/.bashrc[/] to activate."
        )
    else:
        console.print(
            "  [success]✓ Installed.[/]"
            " Run [primary]source ~/.zshrc[/] to activate."
        )
        console.print(
            "  [muted]For powerlevel10k: add [/][primary]cc_env[/]"
            "[muted] to POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS in ~/.p10k.zsh[/]"
        )


# ── Top-level wizard ──────────────────────────────────────────────────


def run(prompter) -> bool:
    """Run the full first-time setup walkthrough.

    Idempotent on re-run: pre-fills current setting values, skips
    already-registered versions, no-ops if shell integration is in place.
    """
    console = get_console()
    log.info("Starting CC configuration wizard...")
    console.print()
    console.print("[heading]CC Configuration Wizard[/]")
    console.print(f"[primary]{'─' * 40}[/]")
    console.print()

    for sdef in _registry():
        _configure_setting(sdef, prompter)

    _configure_versions(prompter)
    _configure_pyenv(prompter)
    _configure_shell_integration(prompter)

    _print_summary(console)
    return True


def _print_summary(console) -> None:
    """Print a summary of what was configured."""
    console.print()
    console.print(f"[primary]{'─' * 40}[/]")
    console.print("[heading]Summary[/]")

    versions = Version.find_by()
    settings_count = len([s for s in Setting.find_by() if s.value])

    console.print(f"  Settings configured: [primary]{settings_count}[/]")
    console.print(f"  Odoo versions found: [primary]{len(versions)}[/]")
    for v in versions:
        path_ok = os.path.isdir(v.path) if v.path else False
        icon = "[success]✓[/]" if path_ok else "[error]✗[/]"
        console.print(f"    {icon} [bold]{v.name}[/] → {v.path or 'no path'}")

    from cc.shell.installer import detect_shell, is_installed
    shell = detect_shell()
    if shell and is_installed(shell):
        console.print(f"  Shell integration:   [success]✓ {shell}[/]")
    elif shell:
        console.print(f"  Shell integration:   [warning]not installed ({shell})[/]")
    else:
        console.print(f"  Shell integration:   [muted]unsupported shell[/]")

    console.print()
    console.print(
        "[success bold]✓ CC is ready.[/]  "
        "[muted]Run 'cc switch PROJECT' to get started.[/]"
    )
    console.print()
