import json
import logging
import os

from cc.base.command import Command
from cc.completion.kinds import CompleteKind
from cc.utils.console import get_console

log = logging.getLogger("CC")


class ModuleCommand(Command):
    group = "project"
    name = "module"
    description = "Set the active env's module list (-i/-u launch mode, -r replace, -l list)."

    def arguments(self):
        return [
            self.Argument(
                ["name"],
                type=str,
                help="Name of module to switch to.",
                nargs="*",
                complete=CompleteKind.MODULE,
            ),
            self.Argument(
                ["-r", "--replace"],
                help="Whether to replace module list or not.",
                action="store_true",
            ),
            self.Argument(
                ["-i", "--install"],
                help="Set launch mode to install (-i).",
                action="store_true",
            ),
            self.Argument(
                ["-u", "--update"],
                help="Set launch mode to update (-u, default).",
                action="store_true",
            ),
            self.Argument(
                ["-l", "--list"],
                help="List active modules for the current environment.",
                action="store_true",
            ),
        ]

    def execute(self):
        log.debug(f"Executing module command with args: {self.args}")

        environment = self.active_environment
        if not environment:
            log.error("No active environment found.")
            return False

        if self.args.list:
            console = get_console()
            active_modules = sorted(environment.module_ids.mapped("name"))
            for m in active_modules:
                console.print(f"[muted]{m}[/]")
            return True

        # Toggle launch mode only — no module selection needed
        if (self.args.install or self.args.update) and not self.args.name and not self.args.replace:
            active_modules = set(environment.module_ids.mapped("name"))
            if not active_modules:
                log.warning("No active modules on this environment.")
                return False
            mode = "-i" if self.args.install else "-u"
            self._write_settings(active_modules)
            console = get_console()
            console.print(f"[success]✓ Launch mode set to {mode} for {len(active_modules)} active modules.[/]")
            return True

        modules, submodules = self.Helpers.get_all_project_modules(self.active_project_path)
        all_modules = modules | submodules

        active_modules = set(environment.module_ids.mapped("name"))
        inactive_modules = all_modules - active_modules

        log.debug(f"Found {len(all_modules)} total modules. {len(active_modules)} active, {len(inactive_modules)} inactive.")

        if not inactive_modules and not self.args.replace:
            console = get_console()
            console.print("[muted]All project modules are already active. No new modules to add.[/]")
            return False

        chosen_modules = []
        if not self.args.name:
            prompt_options = sorted(all_modules) if self.args.replace else sorted(inactive_modules)
            prompt_options = ["Select all"] + prompt_options
            chosen_modules = self.prompter.prompt_checkbox(options=prompt_options, label="Choose a Module")
            if not chosen_modules:
                console = get_console()
                console.print("[muted]No modules selected. Aborting.[/]")
                return False
            if "Select all" in chosen_modules:
                chosen_modules = list(all_modules) if self.args.replace else list(inactive_modules)
        else:
            chosen_modules = list(self.args.name)

        chosen_modules_set = set(chosen_modules)

        if self.args.name and not (chosen_modules_set & all_modules):
            log.error(f"None of the specified modules {chosen_modules_set} were found in the project.")
            return False

        if self.args.replace:
            final_modules = chosen_modules_set
        else:
            final_modules = chosen_modules_set | active_modules

        self._update_environment_modules(environment, final_modules)
        self._write_settings(final_modules)
        return True

    def _update_environment_modules(self, environment, final_modules):
        if self.args.replace:
            vals = [(5, 0, 0)] + [(0, 0, {"name": m}) for m in final_modules]
        else:
            existing = {m.name for m in environment.module_ids}
            new = final_modules - existing
            vals = [(0, 0, {"name": m}) for m in new]

        if vals:
            from cc.daemon.client import call
            call("env.update_modules", env_id=environment.id, module_ids=vals)

    def _write_settings(self, final_modules: set):
        version = self.active_version
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
            settings["cc.modules"] = ",".join(sorted(final_modules))
            if self.args.install:
                settings["cc.initMode"] = "-i"
            elif self.args.update:
                settings["cc.initMode"] = "-u"
            else:
                settings.setdefault("cc.initMode", "-u")
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
            log.debug(f"Updated cc.modules={settings['cc.modules']} cc.initMode={settings['cc.initMode']} in settings.json")
        except Exception as e:
            log.warning(f"Could not update settings.json: {e}")
