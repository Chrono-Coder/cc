"""Create an Odoo database from a dump or fresh initialization."""

import logging
import os
import subprocess
from pathlib import Path

from cc.daemon.client import call
from cc.runtime import OdooRuntime
from cc.utils.console import get_console

from .initdb_command import InitdbCommand

log = logging.getLogger("CC")


_FRESH_DATABASE = "Fresh database"


class CreateDatabaseCommand(InitdbCommand):
    group = "db"
    name = "create"
    description = "Create an Odoo database from a project dump or fresh initialization."

    def arguments(self):
        return [
            self.Argument(["name"], type=str, help="Name of the new database."),
            self.Argument(
                ["--modules", "-i"],
                type=str,
                help="Comma-separated modules to install; skips the interactive picker.",
            ),
            self.Argument(
                ["--no-module-picker"],
                action="store_true",
                help="Initialize only base without opening the project module picker.",
            ),
            self.Argument(
                ["--fresh"],
                action="store_true",
                help="Skip dump selection and create a fresh database.",
            ),
            self.Argument(
                ["--dump"],
                type=str,
                help="Restore a specific Odoo dump zip instead of opening the source picker.",
            ),
            self.Argument(
                ["--with-demo"], action="store_true", help="Load Odoo demo data."
            ),
        ]

    def execute(self):
        env = self.active_environment
        if not env:
            log.error("No active environment. Run `cc switch` first.")
            return False

        name = self.args.name
        try:
            if call("pg.database_exists", name=name):
                log.error(f"Database '{name}' already exists. Choose another name or drop it first.")
                return False
        except Exception as exc:
            log.error(str(exc))
            return False

        dump_path = self._select_database_source()
        if dump_path is False:
            get_console().print("[muted]Database creation cancelled.[/]")
            return False
        if dump_path:
            restored = self._restore(Path(dump_path), name)
            if not restored:
                return False
            call("env.use_database", env_id=env.id, database_name=name)
            get_console().print(f"[success]✓ Database '{name}' restored and selected.[/]")
            return True

        module_actions = self._select_module_actions()
        if module_actions is None:
            get_console().print("[muted]Database creation cancelled.[/]")
            return False

        try:
            runtime = OdooRuntime.from_command(self, database=name)
        except Exception as exc:
            log.error(str(exc))
            return False

        installs = sorted(module for module, action in module_actions.items() if action == "install")
        upgrades = sorted(module for module, action in module_actions.items() if action == "upgrade")
        install_args = sorted({"base", *installs})

        argv = runtime.command("server", dev=False, include_module_actions=False)
        argv.extend(["-i", ",".join(install_args)])
        if upgrades:
            argv.extend(["-u", ",".join(upgrades)])
        argv.append("--stop-after-init")
        if not self.args.with_demo:
            argv.append("--without-demo=all")

        get_console().print(f"[muted]Creating fresh Odoo database[/] [db]{name}[/]")
        try:
            result = subprocess.run(argv, cwd=runtime.cwd)
        except OSError as exc:
            log.error(f"Could not initialize database: {exc}")
            return False
        if result.returncode != 0:
            log.error(f"Odoo database initialization exited with code {result.returncode}.")
            return False

        call("env.use_database", env_id=env.id, database_name=name)
        if module_actions:
            call(
                "env.update_modules",
                env_id=env.id,
                module_ids=[(5, 0, 0)] + [
                    (0, 0, {"name": module, "state": action})
                    for module, action in sorted(module_actions.items())
                ],
            )
        get_console().print(f"[success]✓ Database '{name}' created and selected.[/]")
        return True

    def _select_database_source(self) -> str | bool | None:
        """Return a dump path, None for fresh, or False when cancelled."""
        if self.args.fresh and self.args.dump:
            log.error("Use either --fresh or --dump, not both.")
            return False
        if self.args.fresh:
            return None
        if self.args.dump:
            dump = Path(self.args.dump).expanduser()
            if not self._ensure_dump(str(dump)):
                log.error(f"Not a valid Odoo dump zip containing dump.sql: {dump}")
                return False
            return str(dump)

        setting = self.setting.find_by(name=self.Constants.CONFIG_DOWNLOAD, limit=1)
        download_dir = setting.value if setting and setting.value else ""
        if not download_dir or not os.path.isdir(download_dir):
            get_console().print("[muted]No configured dump directory found; creating a fresh database.[/]")
            return None

        dumps = [path for path in Path(download_dir).rglob("*.zip") if self._ensure_dump(str(path))]
        project_name = (self.active_project.name if self.active_project else "").lower()
        dumps.sort(
            key=lambda path: (
                0 if project_name and project_name in path.name.lower() else 1,
                -path.stat().st_mtime,
                path.name.lower(),
            )
        )
        if not dumps:
            get_console().print("[muted]No valid Odoo dumps found; creating a fresh database.[/]")
            return None

        options = [_FRESH_DATABASE, *[str(path) for path in dumps]]
        selected = self.prompter.prompt_input_multi(
            options,
            "Choose a database source (project dumps shown first)",
        )
        if not selected:
            return False
        return None if selected == _FRESH_DATABASE else selected

    def _select_module_actions(self) -> dict[str, str] | None:
        """Pick active-project modules and assign install/upgrade/draft."""
        if self.args.modules:
            modules = [module.strip() for module in self.args.modules.split(",") if module.strip()]
            return {module: "install" for module in modules if module != "base"}
        if self.args.no_module_picker:
            return {}

        modules, submodules = self.Helpers.get_all_project_modules(self.active_project_path)
        available = sorted(modules | submodules)
        if not available:
            get_console().print("[muted]No custom modules found in the active project; initializing base only.[/]")
            return {}

        chosen = self.prompter.prompt_checkbox(
            options=["Select all", *available],
            label="Choose project modules to configure",
        )
        if chosen is None:
            return None
        if "Select all" in chosen:
            chosen = available

        actions: dict[str, str] = {}
        action_options = ["Install", "Upgrade", "Draft"]
        for module in sorted(chosen):
            action = self.prompter.prompt_input_multi(
                action_options,
                f"Action for {module}",
            )
            if not action:
                return None
            actions[module] = action.lower()
        return actions
