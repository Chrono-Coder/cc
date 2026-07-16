"""Build Odoo process arguments from the active cc environment."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

from cc.utils.errors import CCError


def _path_python() -> str | None:
    """Resolve the user's Python without reusing CC's own virtualenv.

    Editable installs and pipx put CC in an isolated environment which does
    not contain Odoo's requirements. If that environment is the active
    ``VIRTUAL_ENV``, remove its bin directory before resolving Python. An
    independently activated Odoo virtualenv is preserved.
    """
    path = os.environ.get("PATH", "")
    virtual_env = os.environ.get("VIRTUAL_ENV")
    cc_owns_active_venv = bool(
        virtual_env and os.path.realpath(virtual_env) == os.path.realpath(sys.prefix)
    )
    env = os.environ.copy()
    if cc_owns_active_venv:
        cc_bin = os.path.realpath(os.path.join(virtual_env, "bin"))
        path = os.pathsep.join(
            entry for entry in path.split(os.pathsep)
            if os.path.realpath(entry) != cc_bin
        )
        env["PATH"] = path
        env.pop("VIRTUAL_ENV", None)

    candidate = shutil.which("python3", path=path)
    if not candidate:
        return None

    # Resolve pyenv/asdf shims to the actual interpreter while using the same
    # sanitized environment that excluded CC's venv.
    try:
        result = subprocess.run(
            [candidate, "-c", "import sys; print(sys.executable)"],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        resolved = result.stdout.strip()
        return resolved or candidate
    except (OSError, subprocess.SubprocessError):
        return candidate


@dataclass(frozen=True)
class OdooRuntime:
    python: str
    odoo_bin: str
    cwd: str
    database: str
    port: str
    addons_path: str
    install_modules: tuple[str, ...] = ()
    upgrade_modules: tuple[str, ...] = ()

    @classmethod
    def from_command(cls, command, database: str | None = None) -> "OdooRuntime":
        """Resolve the executable and arguments from a Command's active state."""
        environment = command.active_environment
        version = command.active_version
        if not environment or not version:
            raise CCError("No active environment. Run `cc switch` first.")
        if not version.path:
            raise CCError(f"Odoo version '{version.name}' has no configured path.")

        odoo_bin = os.path.join(
            version.path,
            command.Constants.ODOO_ODOO,
            command.Constants.ODOO_ODOOBIN,
        )
        if not os.path.isfile(odoo_bin):
            raise CCError(f"odoo-bin not found at: {odoo_bin}")

        # CC is commonly installed in its own pipx/venv environment. That
        # interpreter only contains CC's dependencies and must not be assumed
        # to contain Odoo's. With no explicitly linked pyenv virtualenv, use
        # the python3 selected by the user's PATH (the same resolution as
        # odoo-bin's ``#!/usr/bin/env python3`` shebang).
        python = _path_python()
        if not python:
            raise CCError("python3 was not found in PATH. Configure one with `cc config venv`.")
        venv = version.pyenv_virtualenv
        if venv and venv != "skip":
            candidate = command.Helpers.pyenv_get_python_path(venv)
            if not os.path.isfile(candidate):
                raise CCError(
                    f"Python for virtualenv '{venv}' not found at: {candidate}. "
                    "Run `cc config venv` to repair the link."
                )
            python = candidate

        db_name = database or (environment.database_id.name if environment.database_id else "")
        if not db_name:
            raise CCError("No database selected. Run `cc db use`, `cc db create`, or `cc db init` first.")

        from cc.services.environment import get_addons_path

        addons_path = get_addons_path(version_id=version.id) or ""
        install_modules = tuple(sorted(
            module.name for module in environment.module_ids
            if (module.state or "draft") == "install"
        ))
        upgrade_modules = tuple(sorted(
            module.name for module in environment.module_ids
            if (module.state or "draft") == "upgrade"
        ))
        return cls(
            python=python,
            odoo_bin=odoo_bin,
            cwd=environment.project_path or version.path,
            database=db_name,
            port=str(version.port or "8069"),
            addons_path=addons_path,
            install_modules=install_modules,
            upgrade_modules=upgrade_modules,
        )

    def command(
        self,
        mode: str,
        extra_args: list[str] | None = None,
        dev: bool = True,
        include_module_actions: bool = True,
    ) -> list[str]:
        args = [self.python, self.odoo_bin]
        if self.addons_path:
            args.append(f"--addons-path={self.addons_path}")
        args.extend(["-p", self.port, "-d", self.database])
        if mode == "shell":
            args.append("shell")
        elif mode == "server" and dev:
            args.append("--dev=all")
        elif mode != "server":
            raise ValueError(f"Unsupported Odoo run mode: {mode}")
        if mode == "server" and include_module_actions:
            if self.install_modules:
                args.extend(["-i", ",".join(self.install_modules)])
            if self.upgrade_modules:
                args.extend(["-u", ",".join(self.upgrade_modules)])
        args.extend(extra_args or [])
        return args
