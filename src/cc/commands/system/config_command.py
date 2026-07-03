"""`cc config` — interactive single-setting picker.

For day-to-day tweaks. `cc config` (no args) shows the settings list
with current values; arrow-pick one, prompts for the new value, saves.

For first-time setup or to walk every step, use `cc setup`.
For dedicated theme / shell tweaks, use `cc config theme` / `cc config shell install`.
"""
import logging

from cc.base.command import Command
from cc.config.schema import settings as schema_settings
from cc.config.wizard import _configure_setting
from cc.utils.console import get_console
from cc.utils.panels import themed_table

log = logging.getLogger("CC")


class ConfigCommand(Command):
    group = "config"          # name == group → bare `cc config` runs this (the picker)
    name = "config"
    description = "Pick and change a single cc setting."

    def arguments(self):
        return [
            self.Argument(
                ["-l", "--list"],
                action="store_true",
                help="List all current settings.",
            ),
        ]

    def execute(self):
        if self.args.list:
            return self._list_settings()
        return self._pick_and_set()

    # ── List ────────────────────────────────────────────────────────

    def _list_settings(self) -> bool:
        console = get_console()
        table = themed_table(title="cc settings")
        table.add_column("Setting", style="bold")
        table.add_column("Value", overflow="fold")

        for sdef in schema_settings():
            if sdef.get("type") == "section":
                continue
            current = self.setting.find_by(name=sdef["key"], limit=1)
            value = current.value if current else "[muted](not set)[/]"
            table.add_row(sdef["label"], value)

        console.print()
        console.print(table)
        console.print()
        return True

    # ── Pick ────────────────────────────────────────────────────────

    def _pick_and_set(self) -> bool:
        """Show 'Choose setting' picker → prompt for value → save.

        Each entry shows the setting label and its current value.
        Selecting one delegates to the wizard's per-setting prompt logic.
        """
        rows = []  # (display_label, sdef)
        for sdef in schema_settings():
            if sdef.get("type") == "section":
                continue
            current = self.setting.find_by(name=sdef["key"], limit=1)
            value = current.value if current else ""
            label = f"{sdef['label']:<32}  {value}"
            rows.append((label, sdef))

        _WORKSPACES_LABEL = "Discover workspaces"
        all_labels = [r[0] for r in rows] + [_WORKSPACES_LABEL]

        choice_label = self.prompter.prompt_input_multi(all_labels, "Choose setting")
        if not choice_label:
            return False

        if choice_label == _WORKSPACES_LABEL:
            return self._configure_workspaces()

        sdef = next((s for label, s in rows if label == choice_label), None)
        if not sdef:
            return False

        _configure_setting(sdef, self.prompter)
        return True

    def _configure_workspaces(self) -> bool:
        from cc.config.wizard import _configure_versions
        _configure_versions(self.prompter)
        return True
