import logging
import os

from cc.base.command import Command

log = logging.getLogger("CC")


class CcCommand(Command):
    name = "cc"
    description = "Open the cc source checkout in your editor (source installs only)."

    def execute(self):
        path = os.path.abspath(os.path.join(self.Constants.PATH_PACKAGE_ROOT, "..", ".."))
        # Only meaningful for a source checkout (install.sh uses pip -e). For a
        # plain site-packages install this path is venv internals - refuse
        # rather than opening junk in the editor.
        if not os.path.isfile(os.path.join(path, "pyproject.toml")):
            log.error("cc source checkout not found (non-editable install?). Nothing to open.")
            return False
        log.debug(f"Opening cc source at: {path}")
        self.Helpers.vs_code(path, new_window=True)
        return True
