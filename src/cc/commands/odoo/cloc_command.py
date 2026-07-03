import logging
import os
import subprocess

from cc.base.arm import Project
from cc.base.command import Command

log = logging.getLogger("CC")


class ClocCommand(Command):
    group = "project"
    name = "cloc"
    description = "Count lines of code for specific modules in the active project."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Get project cloc: cc project cloc NAME",
                nargs="?",
                complete=Project,
            ),
            self.Argument(
                ["-a", "--active"],
                help="Cloc only the active modules (skip picker).",
                action="store_true",
            ),
        ]
        return arguments

    def execute(self):
        log.debug(f"Executing cloc command with args: {self.args}")

        # 1. Find odoo-bin
        odoo_bin_path = False
        if odoo_bin_paths := self.Helpers.search_subdir_file(
            self.active_version.path, self.Constants.ODOO_ODOOBIN, True
        ):
            odoo_bin_path = odoo_bin_paths[0]

        if not odoo_bin_path:
            log.error(f"No odoo-bin found for active version '{self.active_version.name}'!")
            return False

        project_alias = self.args.name
        project_id = self.active_project
        if project_alias:
            project_id = self.project.find_by(name=project_alias, limit=1)
            if not project_id:
                log.error(f"Project '{project_alias}' not found.")
                return False

        if project_id == self.active_project:
            environment = self.active_environment
        else:
            unique_versions = set(project_id.environment_ids.mapped(lambda env: env.version_id.id))
            if len(unique_versions) == 1:
                environment = project_id.environment_ids[0] if project_id.environment_ids else None
            else:
                environment = self.project_environment_selector(
                    project_id, lambda env: env.version_id.id in unique_versions
                )
        if not environment:
            from cc.utils.console import get_console
            console = get_console()
            console.print("[warning]No environment found.[/] Aborting cloc.")
            return False

        env_path = environment.project_path

        if self.args.active:
            active_modules = environment.module_ids.mapped("name")
            if not active_modules:
                log.warning("No active modules on this environment.")
                return True
            final_selection = []
            internal_dir = self.Helpers.get_internal_addons_dir()
            for mod in sorted(active_modules):
                # Check internal first, then project root
                internal_path = os.path.join(env_path, internal_dir, mod) if internal_dir else ""
                root_path = os.path.join(env_path, mod)
                if internal_path and os.path.isdir(internal_path):
                    final_selection.append({"name": mod, "path": internal_path})
                elif os.path.isdir(root_path):
                    final_selection.append({"name": mod, "path": root_path})
                else:
                    log.debug(f"Module '{mod}' not found on disk, skipping.")
        else:
            modules, submodules = self.Helpers.get_all_project_modules(env_path)

            all_module_choices = []
            all_module_choices.append({"name": "Select all", "path": "__ALL__"})

            # Sets are unordered — sort so the picker lists modules the same way
            # every run (the founder's "lists aren't sorted the same each time").
            for mod in sorted(modules):
                path = os.path.join(env_path, mod)
                all_module_choices.append({"name": mod, "path": path})

            internal_dir = self.Helpers.get_internal_addons_dir()
            for sub in sorted(submodules):
                path = os.path.join(env_path, internal_dir, sub)
                all_module_choices.append({"name": sub, "path": path})

            if len(all_module_choices) <= 1:
                log.warning("No modules found in this project.")
                return True

            columns = [
                {"key": "name", "width": 40, "style": "class:col.main"},
            ]

            def format_module(mod_dict):
                return mod_dict

            selected_modules = self.prompter.prompt_checkbox(
                options=all_module_choices, label="Select modules to scan", columns=columns, format_func=format_module
            )

            if not selected_modules:
                from cc.utils.console import get_console
                console = get_console()
                console.print("[muted]No modules selected. Aborting cloc.[/]")
                return True

            is_all_selected = any(m["path"] == "__ALL__" for m in selected_modules)

            if is_all_selected:
                final_selection = [m for m in all_module_choices if m["path"] != "__ALL__"]
            else:
                final_selection = selected_modules

        paths_arg = " ".join([f"-p {m['path']}" for m in final_selection])

        # Resolve the Python interpreter that has odoo's deps installed.
        # subprocess spawns /bin/sh so pyenv shims are not on PATH — we need
        # the absolute path to the right python binary.
        python_bin = self._resolve_python_for_version(environment.version_id, odoo_bin_path)
        if python_bin:
            full_cmd = f"{python_bin} {odoo_bin_path} cloc {paths_arg}"
        else:
            full_cmd = f"{odoo_bin_path} cloc {paths_arg}"

        self.run_cloc(f"CLOC Report ({len(final_selection)} modules)", full_cmd)

        return True

    def _resolve_python_for_version(self, version, odoo_bin_path: str) -> str | None:
        """
        Find a Python binary that has odoo's deps installed, trying:
          1. A .venv/venv directory next to the version path or odoo-bin
          2. The pyenv virtualenv configured for the version (if babel is importable)
        Returns the absolute path to python, or None to let the shell decide.
        """
        import shutil

        candidates = []

        # 1. Look for a conventional venv alongside the version root or odoo-bin
        for base in {os.path.dirname(odoo_bin_path), version.path}:
            for venv_dir in (".venv", "venv"):
                python = os.path.join(base, venv_dir, "bin", "python")
                candidates.append(python)
            # One level up (e.g. version.path = /home/odoo/v18/odoo → check /home/odoo/v18)
            parent = os.path.dirname(base)
            for venv_dir in (".venv", "venv"):
                python = os.path.join(parent, venv_dir, "bin", "python")
                candidates.append(python)

        # 2. pyenv virtualenv configured for this version
        venv_name = version.pyenv_virtualenv
        if venv_name and venv_name != "skip" and self.Helpers.pyenv_is_installed():
            candidates.append(self.Helpers.pyenv_get_python_path(venv_name))

        for python in candidates:
            if not os.path.exists(python):
                continue
            # Quick sanity: check babel is importable (proxy for "odoo deps installed")
            probe = subprocess.run(
                [python, "-c", "import babel"],
                capture_output=True,
            )
            if probe.returncode == 0:
                log.debug(f"Using Python for cloc: {python}")
                return python
            log.debug(f"Skipping {python} — missing odoo deps")

        # Fallback: let the shell pick (works if PYENV_VERSION is set and venv is complete)
        system_python = shutil.which("python3") or shutil.which("python")
        if system_python:
            probe = subprocess.run([system_python, "-c", "import babel"], capture_output=True)
            if probe.returncode == 0:
                return system_python

        # Nothing viable found — warn and return None (subprocess will use whatever's on PATH)
        log.warning(
            f"No Python with odoo deps found for version '{version.name}'. "
            f"Run: pip install -r {version.path}/requirements.txt  (in the correct virtualenv)"
        )
        return None

    def run_cloc(self, cmd_title, cmd):
        """
        Runs the odoo cloc command and prints a parsed table.
        Columns: Module | Code Lines
        """
        from cc.utils.console import get_console
        from cc.utils.panels import themed_table

        console = get_console()
        console.print()
        console.print(f"[heading]{cmd_title}[/]")

        try:
            from cc.utils.ui import Spinner
            log.debug(f"Running cloc command: {cmd}")
            with Spinner("Counting lines of code"):
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            output = result.stdout
            error = result.stderr
            if not output:
                log.debug("Failed to get cloc output.")
                if error:
                    log.error(f"CLOC Error: {error}")
                return

            lines = output.splitlines()
            if not lines:
                log.debug("No lines from cloc output.")
                return

            table = themed_table(show_footer=False)
            table.add_column("Module", max_width=50, overflow="ellipsis", no_wrap=True)
            table.add_column("Code Lines", justify="right")

            total_row = None
            for line in lines:
                parts = line.split()
                if not parts or parts[0].startswith("---") or parts[0] == "Odoo":
                    continue

                if len(parts) == 3 and parts[0].isdigit():
                    total_row = parts[2]
                    continue

                if len(parts) >= 4:
                    name = parts[0]
                    table.add_row(name, parts[-1])

            if total_row is not None:
                table.add_section()
                table.add_row(
                    "[success bold]TOTAL[/]",
                    f"[success bold]{total_row}[/]",
                )

            console.print(table)
            console.print()

        except Exception as e:
            log.error(f"Failed to run cloc: {e}")
