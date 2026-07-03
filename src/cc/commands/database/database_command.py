"""The `cc db` group — set/list/rename/link/unlink/extend the active env's
databases, plus the connection check. Lifecycle verbs (drop/init/copy/restore/
backup) live in their own files, also under `group = "db"`.
"""
import json
import logging
import os

from cc.base.arm import Database
from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.helpers import Helpers

log = logging.getLogger("CC")


def _get_cc_copied_names() -> set:
    """db_names that have a live `<name>-CC-COPY` database, from the metadata cache."""
    from cc.base.arm.database import Database
    from cc.base.db import database_connection_manager
    try:
        with database_connection_manager():
            rows = Database.find_by()
        return {d.name.removesuffix("-CC-COPY") for d in rows
                if d.in_pg and d.name.endswith("-CC-COPY")}
    except Exception:
        return set()


def _write_settings(version, db_name: str) -> None:
    """Mirror the chosen db into the version's .vscode/settings.json (cc.database)."""
    if not version:
        log.warning("No active version — cannot update settings.json.")
        return
    vscode_dir = os.path.join(version.path, ".vscode")
    settings_path = os.path.join(vscode_dir, "settings.json")
    os.makedirs(vscode_dir, exist_ok=True)
    try:
        settings = {}
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                settings = json.load(f)
        settings["cc.database"] = db_name
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=4)
        log.debug(f"Updated cc.database in settings.json: {db_name}")
    except Exception as e:
        log.warning(f"Could not update settings.json: {e}")


class UseCommand(Command):
    group = "db"
    name = "use"
    description = "Set the active database for the current environment."

    def arguments(self):
        return [
            self.Argument(
                ["name"], type=str, nargs="?", complete=Database,
                help="Database to set active. Omit to pick from a list.",
            ),
            self.Argument(
                ["-p", "--pool"], action="store_true",
                help="When prompting, show only databases linked to the current environment.",
            ),
        ]

    def execute(self):
        active_proj = self.active_project
        if not active_proj:
            log.error("There is no active project. Switch to one first with 'cc switch <project>'.")
            return False

        chosen_db_name = self.args.name
        if not chosen_db_name:
            active_env = self.active_environment
            if self.args.pool and active_env:
                pool = active_env.database_ids
                if not pool:
                    log.warning("No databases in the pool. Add some with 'cc db link <name>'.")
                    return False
                db_names = [db.name for db in pool]
            else:
                db_names = Helpers.get_relevant_project_db_names(active_proj.name)
                if not db_names:
                    log.warning(f"No relevant PostgreSQL databases for project '{active_proj.name}'.")
                    return False

            backed_up = _get_cc_copied_names()
            chosen_db_name = self.prompter.prompt_input_multi(
                db_names, "Choose a database",
                format_func=lambda n: {"name": f"{n} ✓" if n in backed_up else n},
            )
            if not chosen_db_name:
                get_console().print("[muted]No database selected. Command aborted.[/]")
                return False

        get_console().print(f"[muted]Setting database to '{chosen_db_name}' for the active environment.[/]")
        _write_settings(self.active_version, chosen_db_name)
        active_env = self.active_environment
        if active_env:
            call("env.use_database", env_id=active_env.id, database_name=chosen_db_name)
        return True


class DbListCommand(Command):
    group = "db"
    name = "list"
    description = "List databases linked to the current environment."

    def execute(self):
        env = self.active_environment
        if not env:
            log.error("No active environment. Run 'cc switch' first.")
            return False

        active_db_id = env.database_id.id if env.database_id else None
        pool = {db.id: db for db in env.database_ids}
        if active_db_id and active_db_id not in pool and env.database_id:
            pool[active_db_id] = env.database_id

        console = get_console()
        if not pool:
            console.print("[warning]No databases linked to this environment.[/] Run [primary]cc db use <name>[/]")
            return True

        from cc.utils.panels import themed_table
        copied = _get_cc_copied_names()
        table = themed_table(title=f"Databases — {env.name}")
        table.add_column("", width=1, justify="center")
        table.add_column("Name")
        table.add_column("Copy", style="warning", justify="center")
        for db in sorted(pool.values(), key=lambda d: d.name):
            is_active = db.id == active_db_id
            table.add_row(
                "●" if is_active else "",
                f"[{'heading' if is_active else 'muted'}]{db.name}[/]",
                "✓" if db.name in copied else "",
            )
        console.print()
        console.print(table)
        console.print()
        return True


class RenameCommand(Command):
    group = "db"
    name = "rename"
    description = "Rename a database (both the cc record and the PostgreSQL database)."

    def arguments(self):
        return [
            self.Argument(["old"], type=str, complete=Database, help="Current database name."),
            self.Argument(["new"], type=str, help="New database name."),
        ]

    def execute(self):
        old, new = self.args.old, self.args.new
        console = get_console()
        try:
            call("database.rename", old=old, new=new)
        except Exception as e:
            log.error(f"Rename failed: {e}")
            return False

        active_env = self.active_environment
        if active_env and active_env.database_id and active_env.database_id.name == new:
            _write_settings(self.active_version, new)
        console.print(f"[success]✓ Renamed: '{old}' → '{new}'[/]")
        return True


class LinkCommand(Command):
    group = "db"
    name = "link"
    description = "Add a database to the current environment's pool (without making it active)."

    def arguments(self):
        return [self.Argument(["name"], type=str, complete=Database, help="Database to link.")]

    def execute(self):
        env = self.active_environment
        if not env:
            log.error("No active environment. Run 'cc switch' first.")
            return False
        call("env.link_database", env_id=env.id, database_name=self.args.name)
        get_console().print(f"[success]✓ Linked '{self.args.name}' to environment '{env.name}'.[/]")
        return True


class UnlinkCommand(Command):
    group = "db"
    name = "unlink"
    description = "Remove a database from the current environment's pool."

    def arguments(self):
        return [self.Argument(["name"], type=str, complete=Database, help="Database to unlink.")]

    def execute(self):
        env = self.active_environment
        if not env:
            log.error("No active environment. Run 'cc switch' first.")
            return False
        call("env.unlink_database", env_id=env.id, database_name=self.args.name)
        get_console().print(f"[success]✓ Unlinked '{self.args.name}' from environment '{env.name}'.[/]")
        return True


class ExtendCommand(Command):
    group = "db"
    name = "extend"
    description = "Push the active database's demo expiry to 2099 and disable the update cron."

    def execute(self):
        env = self.active_environment
        if not env or not env.database_id:
            log.error("No active environment with a linked database. Run 'cc switch' first.")
            return False

        console = get_console()
        db_name = env.database_id.name
        console.print(f"[muted]Extending demo expiry on '{db_name}'...[/]")
        try:
            call("database.extend", db=db_name)
        except Exception as e:
            log.error(f"Extend failed: {e}")
            return False
        console.print("[success]✓ Done — expiry set to 2099, update cron disabled.[/]")
        return True


class CheckCommand(Command):
    group = "db"
    name = "check"
    description = "Diagnose the Postgres connection — show how cc connects (or why it can't)."

    def execute(self):
        from cc.utils.panels import themed_table
        console = get_console()
        results = call("pg.check")

        table = themed_table(title="Postgres connection check")
        table.add_column("", width=1, justify="center")
        table.add_column("Method")
        table.add_column("Result")
        winner_shown = False
        for r in results:
            ok = r.get("ok")
            mark = "[success]●[/]" if ok else "[muted]○[/]"
            if ok and not winner_shown:
                detail = "[success]connects (cc uses this)[/]"
                winner_shown = True
            elif ok:
                detail = "[muted]connects[/]"
            else:
                detail = f"[muted]{r.get('error') or 'failed'}[/]"
            table.add_row(mark, r.get("method", "?"), detail)

        console.print()
        console.print(table)
        if not winner_shown:
            console.print(
                "\n[warning]No connection method worked.[/] If PG runs via Docker (or needs a password), "
                "set a DSN with [primary]cc config[/] → [primary]pg.connection[/] "
                "(e.g. [muted]host=localhost port=5432 user=postgres password=…[/])."
            )
        console.print()
        return winner_shown
