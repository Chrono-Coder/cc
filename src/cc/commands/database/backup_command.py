import logging
import os
import re
import subprocess
from datetime import datetime

from cc.base.arm import Environment
from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.console import get_console

log = logging.getLogger("CC")


class BackupCommand(Command):
    group = "db"
    name = "backup"
    description = "Create and manage named DB snapshots for an environment."

    def arguments(self):
        return [
            self.Argument(
                ["action"],
                type=str,
                nargs="?",
                choices=["create", "list", "restore", "delete"],
                help="Action: create, list, restore, delete. Defaults to list.",
            ),
            self.Argument(
                ["env"],
                type=str,
                nargs="?",
                help="Environment name. Defaults to the active environment.",
                complete=Environment,
            ),
            self.Argument(
                ["--name", "-n"],
                type=str,
                help="Name for the backup (create only).",
            ),
            self.Argument(
                ["--note"],
                type=str,
                help="Optional note to attach to the backup (create only).",
            ),
        ]

    def execute(self):
        action = self.args.action or "list"

        if action == "list" and not self.args.env:
            return self._list(None)

        env = self._resolve_env()
        if not env:
            return False

        if action == "create":
            return self._create(env)
        if action == "list":
            return self._list(env)
        if action == "restore":
            return self._restore(env)
        if action == "delete":
            return self._delete(env)

    # ── Resolve environment ──────────────────────────────────────────────────

    def _resolve_env(self):
        if self.args.env:
            env = self.environment.find_by(name=self.args.env, limit=1)
            if not env:
                log.error(f"Environment '{self.args.env}' not found.")
            return env
        env = self.active_environment
        if not env:
            log.error("No active environment. Run 'cc switch' first or pass an environment name.")
        return env

    # ── Create ───────────────────────────────────────────────────────────────

    def _create(self, env):
        db_name = env.database_id and env.database_id.name
        if not db_name:
            log.error(f"Environment '{env.name}' has no linked database. Run 'cc db use' to set one.")
            return False

        db_id = env.database_id.id if env.database_id else None
        existing = self.backup.find_by(database_id=db_id) if db_id else self.backup.find_by(env_name=env.name)
        if existing and len(existing) >= 5:
            log.warning(
                f"Environment '{env.name}' already has {len(existing)} backups. "
                "Consider deleting old ones with: cc db backup delete"
            )

        now = datetime.now()
        backup_name = self.args.name or f"{env.name}-{now.strftime('%Y-%m-%d-%H%M')}"
        sanitized = re.sub(r"[^\w\-]", "_", backup_name).lower()
        file_name = f"{now.strftime('%Y%m%d_%H%M%S')}_{sanitized}.dump"

        backup_dir = os.path.join(self.Constants.PATH_BACKUPS, env.name)
        os.makedirs(backup_dir, exist_ok=True)
        file_path = os.path.join(backup_dir, file_name)

        from cc.utils.ui import Spinner
        with Spinner(f"Backing up '{db_name}'"):
            result = subprocess.run(
                ["pg_dump", "-Fc", db_name, "-f", file_path],
                capture_output=True, text=True,
            )
        if result.returncode != 0:
            log.error(f"pg_dump failed: {result.stderr.strip()}")
            return False

        size_bytes = os.path.getsize(file_path)

        odoo_version = None
        if env.version_id:
            odoo_version = str(env.version_id.name)

        call(
            "backup.create",
            name=backup_name,
            note=self.args.note or None,
            env_name=env.name,
            db_name=db_name,
            database_id=env.database_id.id if env.database_id else 0,
            file_path=file_path,
            size_bytes=size_bytes,
            created_at=now.isoformat(),
            odoo_version=odoo_version,
        )

        console = get_console()
        console.print(f"[success]✓ Backup created: {file_path} ({self._fmt_size(size_bytes)})[/]")
        return True

    # ── List ─────────────────────────────────────────────────────────────────

    def _list(self, env):
        if env:
            backups = self._backups_for_env(env)
            label = env.database_id.name if env.database_id else env.name
            if not backups:
                console = get_console()
                console.print(f"[warning]No backups found for database '{label}'.[/]")
                return True
            self._print_backups(backups)
        else:
            backups = self.backup.find_by()
            if not backups:
                console = get_console()
                console.print("[warning]No backups found.[/] Run [primary]cc db backup create[/]")
                return True
            by_db = {}
            for b in backups:
                by_db.setdefault(b.db_name, []).append(b)
            for db_name, items in sorted(by_db.items()):
                self._print_backups(items, title=db_name)
        return True

    def _print_backups(self, backups, title=None):
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table

        console = get_console()
        table = themed_table(
            title=title or "",
            title_style="bold",
            border_style="muted",
        )
        table.add_column("#", style="primary", justify="right", width=3)
        table.add_column("Name")
        table.add_column("Date", style="muted")
        table.add_column("Size", style="muted", justify="right")
        table.add_column("DB")
        table.add_column("Note", style="muted", overflow="fold")

        for i, b in enumerate(backups, 1):
            date = b.created_at[:16].replace("T", " ") if b.created_at else ""
            size = self._fmt_size(b.size_bytes)
            table.add_row(
                str(i),
                b.name or "",
                date,
                size,
                b.db_name or "",
                b.note or "",
            )
        console.print()
        console.print(table)

    # ── Restore ──────────────────────────────────────────────────────────────

    def _restore(self, env):
        console = get_console()
        backups = self._backups_for_env(env)
        if not backups:
            console.print(f"[warning]No backups found for '{env.name}'.[/]")
            return True

        choices = [
            f"{b.name}  ({b.created_at[:16].replace('T', ' ')}  {self._fmt_size(b.size_bytes)})"
            for b in backups
        ]
        chosen_label = self.prompter.prompt_input_multi(choices, "Select backup to restore")
        if not chosen_label:
            console.print("[muted]Restore aborted.[/]")
            return False

        chosen = backups[choices.index(chosen_label)]

        if not os.path.exists(chosen.file_path):
            log.error(f"Backup file not found: {chosen.file_path}")
            return False

        if not self.prompter.prompt_confirm(
            f"Restore '{chosen.name}' → '{chosen.db_name}'? This will DROP and recreate the database."
        ):
            console.print("[muted]Restore aborted.[/]")
            return False

        from cc.utils.ui import Spinner
        with Spinner(f"Restoring '{chosen.name}' → '{chosen.db_name}'"):
            drop_result = subprocess.run(["dropdb", "--if-exists", chosen.db_name], capture_output=True, text=True)
            if drop_result.returncode != 0:
                log.error(f"dropdb failed: {drop_result.stderr.strip()}")
                return False

            result = subprocess.run(["createdb", chosen.db_name], capture_output=True, text=True)
            if result.returncode != 0:
                log.error(f"createdb failed: {result.stderr.strip()}")
                return False

            result = subprocess.run(
                ["pg_restore", "-Fc", "-d", chosen.db_name, chosen.file_path],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                log.error(f"pg_restore failed: {result.stderr.strip()}")
                return False

        console.print(f"[success]✓ Restore complete: '{chosen.name}' → '{chosen.db_name}'.[/]")
        return True

    # ── Delete ───────────────────────────────────────────────────────────────

    def _delete(self, env):
        console = get_console()
        backups = self._backups_for_env(env)
        if not backups:
            console.print(f"[warning]No backups found for '{env.name}'.[/]")
            return True

        choices = [
            f"{b.name}  ({b.created_at[:16].replace('T', ' ')}  {self._fmt_size(b.size_bytes)})"
            for b in backups
        ]
        chosen_label = self.prompter.prompt_input_multi(choices, "Select backup to delete")
        if not chosen_label:
            console.print("[muted]Delete aborted.[/]")
            return False

        chosen = backups[choices.index(chosen_label)]

        if not self.prompter.prompt_confirm(f"Delete backup '{chosen.name}'? This cannot be undone."):
            console.print("[muted]Delete aborted.[/]")
            return False

        if os.path.exists(chosen.file_path):
            os.remove(chosen.file_path)

        call("backup.delete", backup_id=chosen.id)
        console.print(f"[success]✓ Deleted backup '{chosen.name}'.[/]")
        return True

    # ── Internal helpers ─────────────────────────────────────────────────────

    def _backups_for_env(self, env):
        """Return backups for an env, keyed by database_id when available, else env_name."""
        if env.database_id:
            return self.backup.find_by(database_id=env.database_id.id)
        return self.backup.find_by(env_name=env.name)

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fmt_size(size_bytes):
        if not size_bytes:
            return "?"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.0f} KB"
        return f"{size_bytes / (1024 * 1024):.1f} MB"
