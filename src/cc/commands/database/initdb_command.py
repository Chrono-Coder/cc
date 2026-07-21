import logging
import os
import shutil
import zipfile
from pathlib import Path

from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.styles import Style

from cc.base.command import Command
from cc.daemon.client import call
from cc.utils.console import get_console
from cc.utils.ui import Spinner

log = logging.getLogger("CC")

_PROMPT_STYLE = Style.from_dict({"": "", "prompt": "fg:ansicyan bold"})


class InitdbCommand(Command):
    group = "db"
    name = "init"
    description = "Create a database from a dump file."
    DB_SEARCH_CUTOFF = 0.54

    def arguments(self):
        return [
            self.Argument(
                ["file_name"],
                type=str,
                help="Initialize DB: cc db init file_name",
                nargs="?",
            ),
            self.Argument(
                ["-n", "--name"],
                type=str,
                help="Initialize DB with custom name: cc db init -n NAME",
            ),
            self.Argument(
                ["-p", "--path"],
                type=str,
                help="Initialize DB under a custom path: cc db init -p PATH",
            ),
        ]

    def execute(self):
        log.debug(f"Executing initdb command with args: {self.args}")

        # ── Resolve search directory ──────────────────────────────────────
        search_dir = self.args.path or ""
        if not search_dir:
            download_setting = self.setting.find_by(name=self.Constants.CONFIG_DOWNLOAD, limit=1)
            if download_setting:
                search_dir = download_setting.value
        if not search_dir:
            log.warning("Download path not configured. Use cc config to set it.")
            return None
        if not os.path.isdir(search_dir):
            log.error(f"Search directory not found: {search_dir}")
            return False

        # ── Find / select the dump file ───────────────────────────────────
        if self.args.file_name:
            db_path_str = self._find_by_name(search_dir, self.args.file_name)
        else:
            db_path_str = self._pick_from_list(search_dir)

        if not db_path_str:
            log.error("No valid database dump selected.")
            return False

        # ── Resolve DB name ───────────────────────────────────────────────
        db_path = Path(db_path_str)
        suggested = (
            self.args.name
            or self.Helpers.clean_word(db_path.stem, self._get_clean_words(), alphabetic=True)
            or db_path.stem
        )
        db_name = self._prompt_db_name(suggested)
        if not db_name:
            log.warning("No database name provided.")
            return False

        console = get_console()
        console.print(f"[muted]Using dump: {db_path.name} → database: {db_name}[/]")

        # ── Restore ───────────────────────────────────────────────────────
        restored = self._restore(db_path, db_name)
        if restored and self.active_environment:
            call(
                "env.use_database",
                env_id=self.active_environment.id,
                database_name=db_name,
            )
            console.print(f"[success]✓ Database '{db_name}' selected for the active environment.[/]")
        return restored

    # ── Dump selection helpers ────────────────────────────────────────────

    def _find_by_name(self, search_dir: str, file_name: str) -> str | None:
        """Fuzzy-search for a named dump; prompt if multiple matches."""
        db_paths = self.Helpers.search_subdir_file(
            search_dir,
            file_name,
            True,
            file_type=".zip",
            strict=False,
            n=5,
            cutoff=self.DB_SEARCH_CUTOFF,
            clean=self._get_clean_words(),
        )
        valid = [p for p in db_paths if self._ensure_dump(p)]
        if not valid:
            log.warning(f"No valid dump found matching '{file_name}'.")
            return None
        if len(valid) == 1:
            return valid[0]
        return self.prompter.prompt_input_multi(valid, "Choose a Database Dump")

    def _pick_from_list(self, search_dir: str) -> str | None:
        """Scan for all valid dumps, sort newest-first, let user pick."""
        all_zips = [str(p) for p in Path(search_dir).rglob("*.zip")]

        valid = [p for p in all_zips if self._ensure_dump(p)]
        if not valid:
            log.warning("No valid dump files found.")
            return None

        sorted_dumps = self.Helpers.sort_files_by_mtime(valid)

        if len(sorted_dumps) == 1:
            console = get_console()
            console.print(f"[muted]Found one dump: {sorted_dumps[0]}[/]")
            return sorted_dumps[0]

        # Format: show filename (truncated) + last-modified date
        def fmt(path):
            from datetime import datetime
            name = Path(path).name
            if len(name) > 44:
                name = name[:41] + "…"
            mtime = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
            return {"name": name, "date": mtime}

        columns = [{"key": "name", "width": 50}, {"key": "date"}]
        chosen = self.prompter.prompt_input_multi(
            sorted_dumps,
            "Choose a Database Dump",
            columns=columns,
            format_func=fmt,
        )
        return chosen

    def _prompt_db_name(self, suggested: str) -> str:
        """Show suggested name; user can accept (Enter) or type a new one."""
        message = FormattedText([
            ("class:prompt", "Database name"),
            ("", f" [{suggested}]: "),
        ])
        try:
            value = prompt(message, style=_PROMPT_STYLE).strip()
        except (KeyboardInterrupt, EOFError):
            return ""
        return value or suggested

    # ── Restore logic ─────────────────────────────────────────────────────

    def _restore(self, db_path: Path, db_name: str) -> bool:
        dir_path = db_path.parent
        extract_path = dir_path / db_name
        dump_sql_path = extract_path / "dump.sql"
        filestore_target = Path.home() / ".local" / "share" / "Odoo" / "filestore" / db_name
        filestore_source = extract_path / "filestore"

        success = False
        try:
            with Spinner(
                text=f"Initializing Database: {db_name}",
                success_text=f"Database {db_name} successfully initialized.",
                fail_text=f"Failed to initialize database {db_name}.",
                debug_mode=self.args.debug,
            ):
                shutil.rmtree(extract_path, ignore_errors=True)
                os.makedirs(extract_path, exist_ok=True)

                try:
                    with zipfile.ZipFile(db_path, "r") as zf:
                        zf.extractall(extract_path)
                    if not dump_sql_path.is_file():
                        raise FileNotFoundError("dump.sql not found in archive")
                except zipfile.BadZipFile:
                    log.error(f"Not a valid zip archive: {db_path}")
                    raise

                # Drop+create+load via the daemon — direct or `docker exec -i psql`
                # (streams the dump into the container), then the cleanup script.
                call(
                    "database.init_from_dump",
                    # Restoring a full Odoo dump streams for minutes — far past the
                    # 10s default; give it a generous ceiling so the client doesn't
                    # time out while the daemon is still loading.
                    timeout=1800,
                    name=db_name,
                    dump_path=str(dump_sql_path),
                    clean_path=str(self.Constants.SQL_CLEANDB_PATH),
                )

                # Filestore is host-specific: copy it for a native Odoo; skip for a
                # dockerized one (its filestore lives in the container/volume — the
                # DB is restored either way).
                if call("pg.backend") == "docker":
                    log.debug("Dockerized Postgres — skipping host filestore copy.")
                else:
                    shutil.rmtree(filestore_target, ignore_errors=True)
                    os.makedirs(filestore_target, exist_ok=True)
                    if filestore_source.is_dir() and any(filestore_source.iterdir()):
                        shutil.copytree(filestore_source, filestore_target, dirs_exist_ok=True)

            success = True

        except FileNotFoundError:
            pass
        except Exception as e:
            log.error(f"Database init failed: {e}")
            log.debug("Traceback:", exc_info=True)
        finally:
            shutil.rmtree(extract_path, ignore_errors=True)

        return success

    # ── Utilities ─────────────────────────────────────────────────────────

    def _ensure_dump(self, path) -> bool:
        if not path or not os.path.exists(path):
            return False
        try:
            with zipfile.ZipFile(path, "r") as zf:
                return "dump.sql" in zf.namelist()
        except (zipfile.BadZipFile, AttributeError, IsADirectoryError, FileNotFoundError):
            return False

    def _get_clean_words(self):
        # Generic dump-name noise + user-configured extras (search.clean_words).
        generic = ["test", "nofs", "odoo", "staging", "main", "production", "fs", "dump"]
        return generic + sorted(self.Helpers.setting_clean_words())
