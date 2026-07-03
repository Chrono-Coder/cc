"""`cc setup` — first-time interactive configuration wizard.

Re-runnable: walks the same flow on a configured machine, pre-filling
current values, skipping shell install if already in place, etc.
"""
import logging

from cc.base.command import Command
from cc.config.wizard import run as run_wizard

log = logging.getLogger("CC")


class SetupCommand(Command):
    name = "setup"
    description = "Run the cc configuration wizard (settings, versions, pyenv, shell, theme)."

    def arguments(self):
        return []

    def execute(self):
        return run_wizard(self.prompter)
