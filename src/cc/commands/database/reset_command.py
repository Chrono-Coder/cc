import logging

from cc.base.arm.common.base_entity import _entity_registry
from cc.base.command import Command
from cc.utils.console import get_console

log = logging.getLogger("CC")


class ResetCommand(Command):
    group = "config"
    name = "reset"
    description = "Deletes CC project management database"

    def execute(self):
        log.debug("Executing reset command.")
        console = get_console()
        if not self.prompter.prompt_confirm("Are you sure you want to delete this database? "):
            console.print("[muted]Database reset aborted by user.[/]")
            return False

        console.print("[muted]Resetting CC project management database...[/]")
        for entity_class in reversed(_entity_registry):
            table_name = entity_class._name
            console.print(f"[muted]Dropping table: {table_name}...[/]")
            self.db.execute(f"DROP TABLE IF EXISTS {table_name};")

        self.db.commit()
        console.print("[success]✓ Database has been successfully reset.[/]")
