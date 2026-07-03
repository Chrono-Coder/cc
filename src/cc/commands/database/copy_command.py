import logging
import os

from cc.base.arm import Database
from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.ui import Spinner

log = logging.getLogger("CC")


class CopyCommand(Command):
    group = "db"
    name = "copy"
    description = "Snapshot a database as <name>-CC-COPY (defaults to the active env's database)."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                type=str,
                help="Copy DB: cc db copy NAME",
                nargs="?",
                complete=Database,
            )
        ]

    def execute(self):
        log.debug(f"Executing copy command with args: {self.args}")
        db_name = self.args.name
        if not db_name:
            # 1. Try active environment's linked database
            active_env = self.active_environment
            if active_env and active_env.database_id and active_env.database_id.name:
                db_name = active_env.database_id.name
                log.debug(f"Using database '{db_name}' from active environment '{active_env.name}'.")
            else:
                # 2. Fall back to version path / settings.json / launch.json detection
                log.debug("No active environment database found, trying version path detection.")
                version_path = self._find_path_in_versions()
                if version_path:
                    db_name = self._get_db_from_launch(version_path)
                if not db_name:
                    log.error("Could not determine database.")
                    console = get_console()
                    console.print("[warning]Specify it with[/] [primary]cc db copy <db_name>[/] [warning]or switch to an environment first.[/]")
                    return False
                log.debug(f"Found database '{db_name}' from settings/launch.json.")

        copy_db_name = f"{db_name}-CC-COPY"
        console = get_console()
        console.print(f"[muted]Preparing to copy database '{db_name}' to '{copy_db_name}'...[/]")

        # Routed through database.copy (direct or docker exec) — CREATE DATABASE
        # … TEMPLATE, dropping any stale copy first. Works on dockerized PG.
        try:
            with Spinner(
                text=f"Copying database '{db_name}' to '{copy_db_name}'",
                success_text=f"Database '{copy_db_name}' created successfully.",
                fail_text=f"Failed to copy database '{db_name}'.",
                debug_mode=self.args.debug,
            ):
                call("database.copy", src=db_name)
        except Exception as e:
            log.error(f"Copy failed: {e}")
            log.debug("Traceback:", exc_info=True)
            return False

        console.print(f"[success]✓ Continue working on your current database '{db_name}'.[/]")
        console.print(f"[muted]Use [primary]cc db restore {db_name}[/primary] to restore the copy ({copy_db_name}) if needed.[/]")
        return True

    def _find_path_in_versions(self):
        target = os.path.abspath(os.getcwd())
        versions = self.version.search([])
        log.debug(f"Searching for version path containing current directory: {target}")
        for version in versions:
            base = os.path.abspath(version.path)
            if os.path.commonpath([target, base]) == base:
                log.debug(f"Found matching version path: {base}")
                return base
        log.debug("No matching version path found for current directory.")
        return False

    def _get_db_from_launch(self, version_path):
        import json

        # Prefer settings.json (written by cc switch) — always has the real values
        settings_path = os.path.join(version_path, ".vscode", "settings.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path) as f:
                    settings = json.load(f)
                db_name = settings.get("cc.database", "").strip()
                if db_name:
                    log.debug(f"Found database '{db_name}' from settings.json.")
                    return db_name
            except Exception as e:
                log.debug(f"Could not read settings.json: {e}")

        # Fallback: parse launch.json args (only works if not using ${config:} variables)
        log.debug(f"Searching for launch.json in: {version_path}")
        launch_path = self.Helpers.search_subdir_file(version_path, self.Constants.ODOO_LAUNCH_JSON, True)
        if not launch_path:
            log.error(f"Failed to find {self.Constants.ODOO_LAUNCH_JSON} in {version_path}")
            return False

        log.debug(f"Reading launch.json: {launch_path[0]}")
        launch_editor = self.JsonEditor(launch_path[0])

        args = launch_editor.get(self.Constants.ODOO_CONFIGURATIONS, self.Constants.ODOO_ARGS)
        if not args:
            log.warning(f"Could not find 'args' list within configurations in {launch_path[0]}")
            return False

        try:
            db_arg_flag = "-d" if "-d" in args else ("--database" if "--database" in args else None)
            if db_arg_flag:
                db_name = args[args.index(db_arg_flag) + 1]
                if db_name.startswith("${"):
                    log.warning("launch.json uses ${config:} variables — could not resolve database name.")
                    return False
                log.debug(f"Found database '{db_name}' from launch.json.")
                return db_name
            log.warning(f"Could not find '-d' or '--database' in launch args: {args}")
            return False
        except (ValueError, IndexError):
            log.warning(f"Error parsing database name from launch args: {args}")
            return False
