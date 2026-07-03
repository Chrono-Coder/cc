import json
import logging
import sqlite3
import sys

from cc.utils.dotenv import load as _load_dotenv
_load_dotenv()

import cc.commands
from cc.base.command import Command
from cc.utils.errors import CCError
# NOTE: cc/api.py is now dead code — remove once VSCode extension is rewritten
from cc.base.db import database_connection_manager, initialize_database


def _run_api(args):
    """Handle `cc api <method>` — proxy through daemon, print JSON result."""
    from cc.daemon.client import call

    if not args:
        print(json.dumps({"error": "No method specified"}))
        return

    try:
        result = call(args[0])
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


def _load_theme():
    """Read theme setting from DB and apply it before any command runs."""
    try:
        from cc.utils.constants import Constants
        from cc.utils.prompter.prompter import update_prompter_style
        conn = sqlite3.connect(Constants.SQLITE_DB_PATH)
        rows = {
            r[0]: r[1]
            for r in conn.execute(
                "SELECT name, value FROM setting WHERE name IN (?,?,?)",
                (Constants.SETTING_THEME, Constants.SETTING_THEME_PRIMARY,
                 Constants.SETTING_THEME_SLIDER),
            ).fetchall()
        }
        conn.close()
        theme = rows.get(Constants.SETTING_THEME, "default")
        console_overrides: dict | None = None
        if theme == "custom":
            from cc.utils.colors import THEMES, CUSTOM_COLORS
            palette = dict(THEMES["custom"])
            primary_rich: str | None = None
            for setting_key, palette_key in (
                (Constants.SETTING_THEME_PRIMARY, "PT_PRIMARY"),
                (Constants.SETTING_THEME_SLIDER,  "PT_SLIDER"),
            ):
                color_name = rows.get(setting_key)
                if color_name and color_name in CUSTOM_COLORS:
                    palette[palette_key] = CUSTOM_COLORS[color_name]["pt"]
                    if palette_key == "PT_PRIMARY":
                        primary_rich = CUSTOM_COLORS[color_name]["rich"]
            THEMES["custom"] = palette
            if primary_rich:
                console_overrides = {
                    "primary": primary_rich,
                    "heading": f"bold {primary_rich}",
                    "header":  primary_rich,
                }
        from cc.utils.console import apply_theme as _apply_console_theme
        _apply_console_theme(theme, overrides=console_overrides)
        update_prompter_style(theme)
    except Exception:
        pass


class Setup:
    def __init__(self):
        with database_connection_manager():
            initialize_database()
        _load_theme()
        with database_connection_manager():
            self._register_commands()
            Command.run()

    def _register_commands(self):
        handlers = Command.build_classes()
        for handler_class in handlers:
            handler_class()


def main():
    try:
        if len(sys.argv) > 1 and sys.argv[1] == "api":
            _run_api(sys.argv[2:])
            return

        Setup()
    except KeyboardInterrupt:
        sys.exit(130)  # conventional 128+SIGINT so scripts see the interrupt
    except CCError as e:
        try:
            from cc.utils.console import get_error_console
            get_error_console().print(f"[error]{e}[/]")
        except Exception:
            print(str(e), file=sys.stderr)
        sys.exit(1)
    except sqlite3.DatabaseError as e:
        try:
            from cc.utils.console import get_error_console
            from cc.utils.constants import Constants
            get_error_console().print(
                f"[error]cc's database is locked or corrupted:[/] {Constants.SQLITE_DB_PATH}\n"
                f"  [muted]{e}[/]\n"
                f"  [muted]Try[/] [primary]cc daemon restart[/][muted] — if it persists, the DB "
                f"file may need to be removed (you'll lose local cc state).[/]"
            )
        except Exception:
            print(f"Database error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Full traceback goes to ~/.cc-cli/logs/cc.log — the console line alone
        # makes bug reports undebuggable.
        logging.getLogger("CC").exception("Unhandled error")
        try:
            from cc.utils.console import get_error_console
            from cc.utils.constants import Constants
            get_error_console().print(
                f"[error]Error:[/] {e}\n"
                f"  [muted]Full traceback: {Constants.PATH_LOG_FILE} (or run cc logs)[/]"
            )
        except Exception:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
