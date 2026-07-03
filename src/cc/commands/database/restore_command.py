import logging

from cc.daemon.client import call
from cc.utils.ui import Spinner

from .copy_command import CopyCommand

log = logging.getLogger("CC")


class RestoreCommand(CopyCommand):
    group = "db"   # explicit: own-attr group doesn't inherit from CopyCommand
    name = "restore"
    description = "Roll a database back to its <name>-CC-COPY snapshot."

    def execute(self):
        log.debug(f"Executing restore command with args: {self.args}")
        db_name = self.args.name

        if not db_name:
            version = self._find_path_in_versions()
            db_name = self._get_db_from_launch(version)

            if not db_name:
                log.error("No DB name found. Try specifying the db name with: cc db restore <db_name>")
                return False
            log.debug(f"No database name specified, found '{db_name}' from launch.json")

        template_db = f"{db_name}-CC-COPY"

        # Routed through database.restore (direct or docker exec): it verifies the
        # template exists in live PG before dropping the target, then CREATE
        # DATABASE … TEMPLATE the copy. Works on dockerized PG. The cache is not
        # gated here — a stale in_pg must not block a restore the service can do.
        try:
            with Spinner(
                text=f"Restoring database '{db_name}' from '{template_db}'",
                success_text=f"Database '{db_name}' restored successfully!",
                fail_text=f"Failed to restore database '{db_name}'.",
                debug_mode=self.args.debug,
            ):
                call("database.restore", src=db_name)
        except Exception as e:
            log.error(f"Restore failed: {e}")
            log.debug("Traceback:", exc_info=True)
            return False

        return True
