import logging
import os
import subprocess

from cc.base.arm import Version
from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.ui import Spinner

log = logging.getLogger("CC")

_ACT = "Activate in current shell"
_REINSTALL = "Reinstall requirements"
_REINIT = "Reinit (change Python version)"
_RENAME = "Rename"
_UNLINK = "Unlink / delete"
_LINK = "Link different venv"

_ACT_NO_VENV = "Link a virtualenv"


class VenvCommand(Command):
    group = "config"
    name = "venv"
    description = "Manage the pyenv virtualenv linked to the active Odoo version."

    def arguments(self):
        return [
            self.Argument(
                ["-v", "--version"],
                type=str,
                metavar="VERSION",
                help="Target a specific version by name instead of the active one.",
                complete=Version,
            ),
        ]

    def execute(self):
        if not self.Helpers.pyenv_is_installed():
            log.error("pyenv is not installed or not in PATH.")
            return False

        if self.args.version:
            version = self.version.find_by(name=self.args.version, limit=1)
            if not version:
                log.error(f"Version '{self.args.version}' not found. Run 'cc config -l' to see configured versions.")
                return False
        else:
            version = self.active_version
            if not version:
                log.error("No active version. Switch to a project first or use -v <version>.")
                return False

        venv = version.pyenv_virtualenv
        exists = bool(venv) and self.Helpers.pyenv_virtualenv_exists(venv)

        self._print_header(version, venv, exists)

        if not venv:
            action = self.prompter.prompt_input_multi([_ACT_NO_VENV], "What would you like to do?")
            if not action:
                return False
            return self._do_link(version)

        actions = [_ACT, _REINSTALL, _REINIT, _RENAME, _UNLINK, _LINK]
        action = self.prompter.prompt_input_multi(actions, "What would you like to do?")
        if not action:
            return False

        if action == _ACT: return self._do_activate(venv)
        if action == _REINSTALL: return self._do_reinstall(version, venv, exists)
        if action == _REINIT: return self._do_reinit(version, venv)
        if action == _RENAME: return self._do_rename(version, venv)
        if action == _UNLINK: return self._do_unlink(version, venv)
        if action == _LINK: return self._do_link(version)

    # ─── Header ───────────────────────────────────────────────

    def _print_header(self, version, venv, exists):
        from cc.utils.console import get_console
        console = get_console()
        console.print()
        console.print(f"  [heading]Virtualenv — {version.name}[/]")
        console.print(f"  [primary]{'─' * 36}[/]")
        console.print()
        if not venv:
            console.print("  [warning]No virtualenv linked.[/]")
            console.print()
            return
        status = "[success]exists[/]" if exists else "[error]missing[/]"
        python_ver = self._get_python_version(venv) or ""
        ver_tag = f"  [muted]{python_ver}[/]" if python_ver else ""
        console.print(f"  [bold]{venv}[/]  {status}{ver_tag}")
        console.print()

    # ─── Actions ──────────────────────────────────────────────

    def _do_activate(self, venv):
        run_file = os.environ.get("CC_RUN_FILE")
        if not run_file:
            log.error("CC_RUN_FILE not set — shell integration required. Source ~/.cc-cli/shell/cc.zsh in your .zshrc.")
            return False
        with open(run_file, "a") as f:
            f.write(f"pyenv activate {venv}\n")
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Activated '{venv}'.[/]")
        return True

    def _do_reinstall(self, version, venv, exists):
        if not exists:
            log.error(f"Virtualenv '{venv}' not found in pyenv.")
            return False
        return self._install_requirements(version, venv)

    def _do_reinit(self, version, venv):
        base = self._pick_python(current_venv=venv)
        if not base:
            return False
        if not self.prompter.prompt_confirm(f"Delete and recreate '{venv}' from Python {base}?"):
            return False
        self._pyenv_delete(venv)
        if not self.Helpers.pyenv_create_virtualenv(base, venv):
            log.error("Failed to recreate virtualenv.")
            return False
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Recreated '{venv}'.[/]")
        return self._install_requirements(version, venv)

    def _do_rename(self, version, old_name):
        new_name = self.prompter.prompt_input_single("New virtualenv name", default=old_name)
        if not new_name or new_name == old_name:
            return False
        base = self._pick_python(current_venv=old_name)
        if not base:
            return False
        if not self.Helpers.pyenv_create_virtualenv(base, new_name):
            log.error("Failed to create new virtualenv.")
            return False
        self._install_requirements(version, new_name)
        self._pyenv_delete(old_name)
        call("version.update", version_id=version.id, pyenv_virtualenv=new_name)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Renamed: '{old_name}' → '{new_name}'[/]")
        return True

    def _do_unlink(self, version, venv):
        if not self.prompter.prompt_confirm(f"Delete '{venv}' and unlink from {version.name}?"):
            return False
        self._pyenv_delete(venv)
        call("version.update", version_id=version.id, pyenv_virtualenv=None)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Deleted and unlinked '{venv}'.[/]")
        return True

    def _do_link(self, version):
        CREATE_NEW = "+ Create new virtualenv"
        current = version.pyenv_virtualenv
        all_venvs = [CREATE_NEW] + self.Helpers.pyenv_list_all_virtualenvs()
        chosen = self.prompter.prompt_autocomplete(
            all_venvs,
            "Choose virtualenv" + (f" (current: {current})" if current else ""),
        )
        if not chosen:
            return False
        if chosen == CREATE_NEW:
            chosen = self._create_new_venv(version)
            if not chosen:
                return False
        else:
            if self.prompter.prompt_confirm(f"Install Odoo requirements into '{chosen}'?"):
                self._install_requirements(version, chosen)
        call("version.update", version_id=version.id, pyenv_virtualenv=chosen)
        from cc.utils.console import get_console
        get_console().print(f"[success]✓ Linked {version.name} → {chosen}[/]")
        return True

    # ─── Helpers ──────────────────────────────────────────────

    def _pick_python(self, current_venv=None) -> str | None:
        detected = self._detect_base_python(current_venv) if current_venv else None
        available = self.Helpers.pyenv_list_versions()
        if not available:
            log.error("No pyenv Python versions installed.")
            return None
        label = "Choose Python version" + (f" (detected: {detected})" if detected else "")
        return self.prompter.prompt_autocomplete(available, label)

    def _create_new_venv(self, version) -> str | None:
        base = self._pick_python()
        if not base:
            return None
        default_name = f"cc-{version.name.lower().replace(' ', '-')}"
        venv_name = self.prompter.prompt_input_single("Virtualenv name", default=default_name)
        if not venv_name:
            return None
        if not self.Helpers.pyenv_create_virtualenv(base, venv_name):
            return None
        if self.prompter.prompt_confirm(f"Install Odoo requirements into '{venv_name}'?"):
            self._install_requirements(version, venv_name)
        return venv_name

    def _install_requirements(self, version, venv_name: str) -> bool:
        req_path = os.path.join(version.path, "odoo", "requirements.txt")
        if not os.path.exists(req_path):
            log.warning(f"No requirements.txt at {req_path}.")
            return False
        pip = self.Helpers.pyenv_get_python_path(venv_name).replace("/python", "/pip")
        try:
            with Spinner(
                text="pip install -r requirements.txt",
                success_text=f"Requirements installed into '{venv_name}'.",
                fail_text="pip install failed.",
                debug_mode=self.args.debug,
            ):
                subprocess.run([pip, "install", "-r", req_path], check=True, capture_output=True)
            return True
        except subprocess.CalledProcessError as e:
            log.error(f"pip install failed: {e}")
            return False

    def _get_python_version(self, venv_name: str) -> str | None:
        try:
            python = self.Helpers.pyenv_get_python_path(venv_name)
            result = subprocess.run([python, "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                return (result.stdout.strip() or result.stderr.strip()).replace("Python ", "")
        except Exception:
            pass
        return None

    def _detect_base_python(self, venv_name: str) -> str | None:
        ver = self._get_python_version(venv_name)
        if not ver:
            return None
        installed = self.Helpers.pyenv_list_versions()
        return next((v for v in installed if v.startswith(ver)), None)

    def _pyenv_delete(self, venv_name: str):
        try:
            subprocess.run(["pyenv", "virtualenv-delete", "-f", venv_name], check=True)
        except subprocess.CalledProcessError as e:
            log.warning(f"Could not delete virtualenv '{venv_name}': {e}")
