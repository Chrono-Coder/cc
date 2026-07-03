import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from cc.base.arm import Environment, Project
from cc.daemon.client import call
from cc.events import EventCancelled, SwitchCheckoutEvent, SwitchEvent, bus
from cc.ide import CcState, active_writers
from cc.services.dto import EnvDetailDTO

from .open_command import OpenCommand

log = logging.getLogger("CC")


class SwitchCommand(OpenCommand):
    name = "switch"
    description = "Switches active project, configures IDE, and opens it."

    def arguments(self):
        arguments = [
            self.Argument(
                ["name"],
                type=str,
                help="Switch Project: cc switch NAME",
                nargs="?",
                complete=Project,
            ),
            self.Argument(
                ["-n", "--new"],
                help="Open Project in New Window: cc switch NAME -n",
                action="store_true",
            ),
            self.Argument(
                ["-s", "--silent"],
                help="Switch project without opening the IDE: cc switch NAME -s",
                action="store_true",
            ),
            self.Argument(
                ["-e", "--env"],
                type=str,
                help="Switch directly to a named environment: cc switch --env ENV_NAME",
                default=None,
                complete=Environment,
            ),
            self.Argument(
                ["--no-pull"],
                action="store_true",
                help="Skip fetch and rebase in R&D repos on switch.",
            ),
            self.Argument(
                ["-a", "--all"],
                action="store_true",
                help="Show all environments in the picker, including merged/archived ones.",
            ),
        ]
        return arguments

    def execute(self):
        log.debug(f"Executing switch command with args: {self.args}")

        self._vscode_terminal = os.environ.get("TERM_PROGRAM") == "vscode"

        # Retire stale envs before building any picker (no-op unless
        # env.auto_stale_days is configured). Keeps the list below short.
        call("env.sweep_stale")

        if self.args.env:
            env_name = self.args.env
            log.debug(f"Looking up environment by name: {env_name}")
            matches = call("env.find_all_by_name", name=env_name)
            if not matches:
                log.error(f"Environment '{env_name}' not found. See all environments with: cc project env list")
                return False
            dtos = [EnvDetailDTO(**m) for m in matches]
            # Non-unique names: a collision pops a project/env picker instead of
            # silently grabbing the first match.
            env_dto = dtos[0] if len(dtos) == 1 else self._pick_by_project(dtos)
            if not env_dto:
                return False
            self._prompt_reactivate(env_dto)
            self._fire_switch_before()
            log.debug(f"Setting active environment to '{env_dto.name}'")
            self.set_active_environment(env_dto.id, env_dto.version_id)
            if self.args.silent:
                return self._perform_ide_configuration()
            return self._perform_switch_actions()

        if self.args.name == "-":
            # `cc switch -` → jump back to the env you were on before this one.
            prev = call("env.get_previous_env")
            if not prev:
                log.error("No previous environment to switch back to.")
                return False
            env_dto = EnvDetailDTO(**prev)
            self._prompt_reactivate(env_dto)
            self._fire_switch_before()
            log.debug(f"Switching back to previous environment '{env_dto.name}'")
            self.set_active_environment(env_dto.id, env_dto.version_id)
            if self.args.silent:
                return self._perform_ide_configuration()
            return self._perform_switch_actions()

        project_name = self.args.name
        if not project_name:
            log.debug("No project name specified — showing recent environment picker.")
            # Load the full recency-ordered set so type-to-filter reaches every
            # env; the picker viewport caps the *initial* view (5, or 10 w/ --all).
            recent_raw = call("env.get_recent_envs", limit=100, include_all=self.args.all)
            if not recent_raw:
                log.debug("No recent envs found, falling back to switch actions on active project.")
                return self._perform_switch_actions()
            recent = [EnvDetailDTO(**e) for e in recent_raw]
            if len(recent) == 1:
                selected = recent[0]
            else:
                from cc.utils.prompter.env_selector import EnvSelectorTUI
                from cc.utils.prompter.prompter import PROMPTER_STYLE
                active = self.active_environment
                active_id = active.id if active else None
                selected = EnvSelectorTUI(
                    environments=recent,
                    project_name="Recent",
                    active_env_id=active_id,
                    style=PROMPTER_STYLE,
                    viewport=10 if self.args.all else 5,
                ).run()
            if not selected:
                log.debug("No environment selected.")
                return False
            self._prompt_reactivate(selected)
            self._fire_switch_before()
            self.set_active_environment(selected.id, selected.version_id)
            if self.args.silent:
                return self._perform_ide_configuration()
            return self._perform_switch_actions()

        projects = self.project.find_by(name=project_name, limit=1)
        project = projects[0] if projects else None
        env_id = None
        env_version_id = None

        if project:
            log.debug(f"Project '{project_name}' found. Selecting environment interactively.")
            envs = call("env.find_by_project_name", project_name=project_name, include_all=self.args.all)
            if not envs:
                if not self.args.all:
                    # Everything may be merged/archived — retry showing all so
                    # the user isn't told a populated project is empty.
                    envs = call("env.find_by_project_name", project_name=project_name, include_all=True)
                if not envs:
                    log.error(f"Project '{project_name}' has no configured environments.")
                    return False
            dto_list = [EnvDetailDTO(**e) for e in envs]
            if len(dto_list) == 1:
                selected = dto_list[0]
            else:
                from cc.utils.prompter.env_selector import EnvSelectorTUI
                from cc.utils.prompter.prompter import PROMPTER_STYLE
                active = self.active_environment
                active_id = (
                    active.id
                    if active and active.project_id and active.project_id.name == project_name
                    else None
                )
                selected = EnvSelectorTUI(
                    environments=dto_list,
                    project_name=project_name,
                    active_env_id=active_id,
                    style=PROMPTER_STYLE,
                    viewport=10 if self.args.all else 5,
                ).run()
            if not selected:
                log.debug("No environment selected.")
                return False
            self._prompt_reactivate(selected)
            env_id = selected.id
            env_version_id = selected.version_id

        else:
            log.warning(f"Project alias '{project_name}' not found in the database. Attempting to discover and create.")
            environment = self._execute_add(project_name=project_name)
            if not environment:
                return False
            project = environment.project_id
            env_id = environment.id
            env_version_id = environment.version_id.id if environment.version_id else None

        self._fire_switch_before()

        log.debug(f"Setting active environment id={env_id} for project '{project_name}'")
        self.set_active_environment(env_id, env_version_id)
        if self.args.silent:
            return self._perform_ide_configuration()
        return self._perform_switch_actions()

    def _prompt_reactivate(self, env_dto) -> None:
        """If switching to a merged/archived env, offer to set it active again.

        Only reached when the user deliberately lands on a non-active env (via
        --all, --env <name>, or a single-env project), so the prompt isn't noise.
        """
        status = getattr(env_dto, "status", None) or "active"
        if status == "active":
            return
        if self.prompter.prompt_confirm(
            f"'{env_dto.name}' is {status}. Set it back to active?", default=True
        ):
            call("env.set_status", env_id=env_dto.id, status="active")
            try:
                env_dto.status = "active"
            except Exception:
                pass

    def _fire_switch_before(self) -> None:
        """Fire the ``switch.before`` event before the active env changes.

        Handlers run in-process and may prompt; one declining raises
        ``EventCancelled``, which aborts the switch.
        """
        prev = self.active_environment
        try:
            bus.emit("switch.before", SwitchEvent(
                prev_env_id=prev.id if prev else None,
                prev_env_name=prev.name if prev else "",
                silent=bool(getattr(self.args, "silent", False)),
            ))
        except EventCancelled:
            raise SystemExit(0) from None

    def _run_hook(self, hook_name: str) -> None:
        """
        Run a switch hook script if it exists and is executable.

        Hooks live in ~/.cc-cli/hooks/ — create pre_switch or post_switch
        as executable shell scripts. The following environment variables are
        available inside the hook:

            CC_ENV_NAME      — environment name (e.g. "internal19")
            CC_PROJECT_NAME  — project name (e.g. "internal")
            CC_PROJECT_PATH  — absolute path to the project directory
            CC_DATABASE      — linked database name (empty if none)
            CC_BRANCH        — git branch name (empty if none)
            CC_VERSION       — Odoo version name (e.g. "19.0")

        Any lines printed to stdout are eval'd in the parent shell, so you
        can activate venvs, set env vars, or run any shell command:

            #!/bin/bash
            echo "source $CC_PROJECT_PATH/.venv/bin/activate"
            echo "export ODOO_DB=$CC_DATABASE"
        """
        hook_path = os.path.join(self.Constants.PATH_HOOKS, hook_name)
        if not os.path.isfile(hook_path) or not os.access(hook_path, os.X_OK):
            return

        env = self.active_environment
        if not env:
            return

        hook_env = os.environ.copy()
        hook_env["CC_ENV_NAME"] = env.name or ""
        hook_env["CC_PROJECT_NAME"] = env.project_id.name if env.project_id else ""
        hook_env["CC_PROJECT_PATH"] = env.project_path or ""
        hook_env["CC_DATABASE"] = env.database_id.name if env.database_id else ""
        hook_env["CC_BRANCH"] = env.branch_name or ""
        hook_env["CC_VERSION"] = env.version_id.name if env.version_id else ""
        hook_env["CC_VERSION_PATH"] = env.version_id.path if env.version_id else ""
        hook_env["CC_NEW_WINDOW"] = "1" if self._will_open_new_window() else "0"

        log.debug(f"Running hook: {hook_path}")
        try:
            result = subprocess.run(
                [hook_path],
                capture_output=True, text=True,
                env=hook_env, timeout=30,
            )
            if result.returncode != 0:
                log.warning(f"Hook '{hook_name}' exited {result.returncode}: {result.stderr.strip()}")
            # Write stdout to CC_RUN_FILE so it's eval'd in the parent shell.
            # This allows hooks to activate venvs, set env vars, etc.
            if result.stdout.strip():
                run_file = os.environ.get("CC_RUN_FILE")
                if run_file:
                    with open(run_file, "a") as f:
                        f.write(result.stdout)
                else:
                    log.debug(f"Hook '{hook_name}' output (CC_RUN_FILE not set): {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            log.warning(f"Hook '{hook_name}' timed out after 30s — skipping.")
        except Exception as e:
            log.warning(f"Hook '{hook_name}' failed: {e}")

    def _perform_switch_actions(self) -> bool:
        """
        Updates the run configuration for the configured IDE and opens it.
        Virtual projects skip all filesystem/IDE actions — timesheet clock only.
        """
        log.debug("Performing post-switch actions (IDE config, open, cd/checkout).")
        if not self.active_project or not self.active_environment:
            log.error("Switch aborted: Missing critical info for the active environment.")
            return False

        is_virtual = bool(getattr(self.active_project, "is_virtual", False))

        if is_virtual:
            from cc.utils.console import get_console
            get_console().print(f"[success]✓ Switched to virtual project '{self.active_project.name}'[/] [muted]— timesheet clock started.[/]")
            return True

        if not self.active_project_path:
            log.error("Switch aborted: Missing project path for the active environment.")
            return False

        self._run_hook("pre_switch")

        python_path = self._setup_pyenv(activate=not self.args.new)

        log.debug("Updating IDE configuration...")
        if not self._apply_ide(python_path):
            log.error("Failed to update IDE configuration.")
            return False
        log.debug("IDE configuration updated successfully.")

        self._open_ide()

        is_rnd = bool(
            self.active_project
            and self.active_project.workspace_id
            and self.active_project.workspace_id.is_rnd
        )

        # Repos where the env branch existed but checkout failed — almost always
        # uncommitted changes. Collected so we don't print a false "✓ Switched".
        checkout_failures: list[str] = []

        if self.active_environment.branch_name and self.active_environment.project_path:
            log.debug(f"Checking out branch: {self.active_environment.branch_name}")
            result = self.run_command(
                ["git", "-C", self.active_environment.project_path, "checkout", self.active_environment.branch_name]
            )
            if result.returncode != 0:
                log.warning(f"git checkout failed: {result.stderr.strip()}")
                # R&D resolves branches per-repo below (the project path may not
                # be a single git repo there), so only the non-R&D single-repo
                # checkout failing is a real, switch-defeating failure here.
                if not is_rnd:
                    repo_label = os.path.basename(self.active_environment.project_path.rstrip("/")) or "project"
                    checkout_failures.append(repo_label)
            else:
                from cc.utils.console import get_console
                get_console().print(f"[muted]Checked out branch '{self.active_environment.branch_name}'[/]")

        # R&D check-out + rebase across the shared Odoo repos is contributed by
        # cc-rnd via this collecting hook; a no-op (empty) when it isn't installed.
        checkout_failures.extend(bus.collect("switch.checkout", SwitchCheckoutEvent(
            env_id=self.active_environment.id,
            version_id=self.active_version.id if self.active_version else None,
            no_pull=self.args.no_pull,
        )))

        # Only cd in the parent shell if we're reusing the current window.
        # When a new window opens, the user moves there — the old terminal's
        # CWD becomes irrelevant, and the new window picks up terminal.integrated.cwd.
        if not self._will_open_new_window():
            log.debug(f"Changing directory to: {self.active_project_path}")
            self.exec_sh_command(f"cd {self.active_project_path}")

        self._trigger_auto_fetch_if_due()
        self._run_hook("post_switch")

        from cc.utils.console import get_console, get_error_console
        env = self.active_environment
        version_name = env.version_id.name if env.version_id else "?"
        branch = env.branch_name or ""
        db = env.database_id.name if env.database_id else ""
        bits = [f"[primary]{version_name}[/]"]
        if branch:
            bits.append(f"[branch]{branch}[/]")
        if db:
            bits.append(f"[db]{db}[/]")
        target = (
            f"[bold]{self.active_project.name}[/] / [bold]{env.name}[/]  "
            f"[muted]·[/]  {'  [muted]·[/]  '.join(bits)}"
        )

        if checkout_failures:
            # The env switched (IDE/cd/settings applied) but the branch did NOT
            # change in these repos. Say so loudly on stderr and fail (exit 1)
            # so the silent wrong-branch trap can't bite scripts or the user.
            get_console().print(f"[warning]⚠ Switched[/] → {target}")
            get_error_console().print(
                f"[warning]Branch '{branch}' not checked out in: "
                f"{', '.join(checkout_failures)}[/]  "
                f"[muted](commit or stash your changes, then re-run cc switch)[/]"
            )
            return False

        get_console().print(f"[success]✓ Switched[/] → {target}")
        return True

    def _will_open_new_window(self) -> bool:
        """Detect whether this switch will open a new VSCode window.

        A new window opens when:
        - The -n flag is explicitly set by the user
        - In a VSCode terminal, the target version root differs from the
          current workspace root (auto -n to avoid closing the current window)
        """
        if self.args.new:
            return True
        if not getattr(self, "_vscode_terminal", False):
            return False
        version_path = ""
        if self.active_environment and self.active_environment.version_id:
            version_path = self.active_environment.version_id.path or ""
        if not version_path:
            return False
        vscode_cwd = os.environ.get("VSCODE_CWD", "")
        if not vscode_cwd:
            return False
        if not vscode_cwd.startswith(version_path):
            log.debug(f"Workspace root change detected ({vscode_cwd} → {version_path}) — auto new window.")
            return True
        return False

    def _trigger_auto_fetch_if_due(self) -> None:
        """Spawn background git fetch for odoo repos if auto-fetch is enabled and interval has elapsed."""
        auto_fetch = self.setting.find_by(name=self.Constants.SETTING_AUTO_FETCH, limit=1)
        if not auto_fetch or auto_fetch.value != "true":
            return

        interval_setting = self.setting.find_by(name=self.Constants.SETTING_AUTO_FETCH_INTERVAL, limit=1)
        try:
            interval_hours = int(interval_setting.value) if interval_setting else 24
        except (ValueError, TypeError):
            interval_hours = 24

        version = self.active_version
        if not version:
            return

        now = datetime.now(timezone.utc)
        if version.last_fetched_at:
            try:
                last = datetime.fromisoformat(version.last_fetched_at)
                if (now - last).total_seconds() < interval_hours * 3600:
                    return
            except (ValueError, TypeError):
                pass

        # Mark fetched now (optimistic) so parallel switches don't double-trigger
        call("version.update", version_id=version.id, last_fetched_at=now.isoformat())

        repos = [self.Constants.ODOO_ODOO, self.Constants.ODOO_ENTERPRISE, self.Constants.ODOO_DESIGN_THEMES]
        versions_to_fetch = [version]
        seen_paths = set()
        for v in versions_to_fetch:
            if not v.path or v.path in seen_paths:
                continue
            seen_paths.add(v.path)
            for repo in repos:
                repo_path = os.path.join(v.path, repo)
                if os.path.isdir(repo_path):
                    subprocess.Popen(
                        ["git", "fetch", "origin"],
                        cwd=repo_path,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True,
                    )
        from cc.utils.console import get_console
        get_console().print(f"[muted]Background fetch triggered (next due in {interval_hours}h).[/]")

    def _get_add_ons(self, version_path, project, is_rnd=False):
        log.debug(f"Calculating addons path for version '{version_path}' and project '{project}' (rnd={is_rnd})")
        odoo_addons = self.Helpers.search_subdir_file(version_path, self.Constants.ODOO_ADDONS, False)
        odoo_odoo_addons = self.Helpers.search_subdir_file(version_path, self.Constants.ODOO_ADDONS, False, skips=1)
        enterprise = self.Helpers.search_subdir_file(version_path, self.Constants.ODOO_ENTERPRISE, False)
        design_themes = self.Helpers.search_subdir_file(version_path, self.Constants.ODOO_DESIGN_THEMES, False)

        # Each repo is optional — a missing one resolves to [] and is filtered out,
        # so a workspace with only odoo (no enterprise/design-themes) works fine.
        paths = [
            odoo_addons[0] if odoo_addons else None,
            odoo_odoo_addons[0] if odoo_odoo_addons else None,
            enterprise[0] if enterprise else None,
            design_themes[0] if design_themes else None,
        ]

        # In R&D mode the addons set is exactly the shared repos above. The
        # "project" is the version root itself, so appending it (and probing for
        # an internal-addons dir under it) only adds a junk trailing entry.
        if not is_rnd:
            paths.append(project)
            internal_dir = self.Helpers.get_internal_addons_dir()
            project_internal = (
                self.Helpers.search_subdir_file(project, internal_dir, False, banned_dirs={".git"})
                if internal_dir else ""
            ) or ""
            if project_internal:
                paths.append(project_internal[0])

        addons_path = ",".join(filter(None, paths))
        log.debug(f"Calculated addons_path: {addons_path}")
        return addons_path

    def _setup_pyenv(self, activate: bool = True) -> str:
        """Detect, prompt, create, and activate a pyenv virtualenv for the active version.

        Returns the absolute python interpreter path, or an empty string if no
        pyenv is configured / available. The returned path is consumed by
        :meth:`_apply_ide` to populate ``python.defaultInterpreterPath`` (or the
        equivalent in other IDEs) via the writer plugin in one pass.
        """
        if not self.Helpers.pyenv_is_installed():
            log.debug("pyenv not installed, skipping Python environment activation.")
            return ""

        version = self.active_version
        if not version:
            return ""

        virtualenv_name = version.pyenv_virtualenv

        # Auto-detect from .python-version file if not yet configured
        if not virtualenv_name:
            detected = self.Helpers.pyenv_detect_version_from_path(version.path)
            if detected:
                log.debug(f"Detected .python-version: {detected}")
                # If it looks like a virtualenv name (not a bare version number), use it directly
                if not re.match(r"^\d+\.\d+", detected):
                    virtualenv_name = detected
                else:
                    # It's a bare version — create a cc-vXX virtualenv from it
                    venv_name = f"cc-{version.name.lower().replace(' ', '-')}"
                    if not self.Helpers.pyenv_virtualenv_exists(venv_name):
                        if self.prompter.prompt_confirm(
                            f"Create pyenv virtualenv '{venv_name}' from Python {detected} for {version.name}?"
                        ):
                            if not self.Helpers.pyenv_create_virtualenv(detected, venv_name):
                                return ""
                        else:
                            call("version.update", version_id=version.id, pyenv_virtualenv="skip")
                            return ""
                    virtualenv_name = venv_name
                call("version.update", version_id=version.id, pyenv_virtualenv=virtualenv_name)

        # First-time setup: no .python-version file and not yet configured
        if not virtualenv_name:
            available = self.Helpers.pyenv_list_versions()
            if not available:
                log.debug("No pyenv versions found, skipping.")
                return ""
            if not self.prompter.prompt_confirm(
                f"No Python environment linked to {version.name}. Set one up with pyenv?"
            ):
                call("version.update", version_id=version.id, pyenv_virtualenv="skip")
                return ""
            base_version = self.prompter.prompt_autocomplete(available, "Choose base Python version")
            if not base_version:
                return ""
            venv_name = f"cc-{version.name.lower().replace(' ', '-')}"
            if not self.Helpers.pyenv_virtualenv_exists(venv_name):
                if not self.Helpers.pyenv_create_virtualenv(base_version, venv_name):
                    return ""
            virtualenv_name = venv_name
            call("version.update", version_id=version.id, pyenv_virtualenv=virtualenv_name)

        # Skip marker — user opted out
        if virtualenv_name == "skip":
            return ""

        if activate:
            from cc.utils.console import get_console
            get_console().print(f"[muted]Activating Python environment: {virtualenv_name}[/]")
            self.exec_sh_command(f"export PYENV_VERSION={virtualenv_name}")

        return self.Helpers.pyenv_get_python_path(virtualenv_name) or ""

    # ── IDE writer integration ───────────────────────────────────────────
    # The actual editor-specific code lives in cc/ide/. This command only
    # builds a CcState snapshot and hands it to the active writers.
    #
    # CRITICAL: `cc switch` MUST NEVER edit launch.json (or other template /
    # run-config files). Per-switch writes go through `writer.apply()` which
    # is contracted to touch only the per-switch dynamic state files
    # (settings.json for VSCode). Templates are written once via
    # `writer.setup()` from `cc workspace add` / `cc config ide setup`.

    def _build_cc_state(self, python_path: str = "") -> "CcState":
        """Snapshot current cc state into the stable contract for IDE writers."""
        version = self.active_version
        environment = self.active_environment
        database = environment.database_id if environment else None

        is_rnd = bool(
            environment
            and environment.project_id
            and environment.project_id.workspace_id
            and environment.project_id.workspace_id.is_rnd
        )
        modules = ",".join(environment.module_ids.mapped("name")) if environment else ""
        addons_path = (
            self._get_add_ons(version.path, environment.project_path, is_rnd=is_rnd)
            if environment and version
            else ""
        )
        odoo_bin = (
            os.path.join(version.path, self.Constants.ODOO_ODOO, self.Constants.ODOO_ODOOBIN)
            if version
            else ""
        )

        # --upgrade-path spans two optional repos: odoo/upgrade-util (src/) and
        # odoo/upgrade (migrations/). Each is independently optional — whichever
        # is present contributes its segment; absent ones are simply omitted.
        upgrade_path = ""
        if version:
            upgrade_parts = []
            util_src = self.Helpers.search_subdir_file(
                self.Helpers.search_subdir_file(version.path, self.Constants.ODOO_UPGRADE_UTIL, False),
                self.Constants.ODOO_SRC,
                False,
            )
            if util_src:
                upgrade_parts.append(util_src[0])
            upgrade_migrations = self.Helpers.search_subdir_file(
                self.Helpers.search_subdir_file(version.path, self.Constants.ODOO_UPGRADE, False),
                self.Constants.ODOO_MIGRATIONS,
                False,
            )
            if upgrade_migrations:
                upgrade_parts.append(upgrade_migrations[0])
            upgrade_path = ",".join(upgrade_parts)

        return CcState(
            workspace_path=str(version.path) if version else "",
            env_name=environment.name if environment else "",
            project_name=(
                environment.project_id.name
                if environment and environment.project_id
                else ""
            ),
            version_name=version.name if version else "",
            branch=environment.branch_name if environment else "",
            db=database.name if database else "",
            odoo_bin=odoo_bin,
            port=str(version.port or "8069") if version else "",
            addons_path=addons_path,
            modules=modules,
            upgrade_path=upgrade_path,
            python_path=python_path,
            project_path=environment.project_path if environment else "",
        )

    def _apply_ide(self, python_path: str = "") -> bool:
        """Project cc state onto every active IDE writer for the current workspace.

        Loops over writers selected by ``cc.ide`` (or auto-detection) and calls
        :meth:`cc.ide.IdeWriter.apply` on each. A writer's failure is logged
        but does not abort the switch — IDE config is non-fatal.
        """
        version = self.active_version
        if not version or not version.path:
            log.debug("No active version; skipping IDE configuration.")
            return True

        workspace = Path(version.path)
        state = self._build_cc_state(python_path)

        writers = active_writers(workspace)
        if not writers:
            log.debug("No IDE writers active for this workspace.")
            return True

        for writer in writers:
            try:
                writer.apply(workspace, state)
            except Exception as e:
                log.warning(f"IDE writer {writer.name!r} apply() failed: {e}")
        return True

    def _perform_ide_configuration(self) -> bool:
        """Used by the ``--silent`` switch path.

        Applies cc state to IDEs without running pyenv setup or any other
        side effects. Equivalent to the full switch's writer pass, minus the
        python_path field.
        """
        return self._apply_ide()
