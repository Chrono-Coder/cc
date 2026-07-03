"""`cc config theme` — pick or set the cc theme."""
import logging

from cc.base.command import Command
from cc.theme.picker import (
    apply_custom_theme,
    apply_named_theme,
    get_current_custom_colors,
    pick_custom_colors,
    run_theme_picker,
)
from cc.utils.colors import THEMES
from cc.utils.console import get_console

log = logging.getLogger("CC")


class ThemeCommand(Command):
    group = "config"
    name = "theme"
    description = "Pick or set the cc theme."

    def arguments(self):
        return [
            self.Argument(
                names=["name"],
                type=str,
                nargs="?",
                default=None,
                choices=list(THEMES.keys()),
                help="Theme name to set directly. Omit to open the interactive picker.",
            ),
        ]

    def execute(self):
        if not self.args.name:
            return run_theme_picker()

        if self.args.name == "custom":
            current_primary, current_slider = get_current_custom_colors()
            result = pick_custom_colors(current_primary, current_slider)
            if not result:
                get_console().print("[muted]Cancelled.[/]")
                return False
            primary, slider = result
            apply_custom_theme(primary, slider)
            return True

        apply_named_theme(self.args.name)
        return True
