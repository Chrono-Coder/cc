import logging
import signal
import sqlite3
from argparse import ArgumentParser
from collections import defaultdict
from functools import cached_property
from typing import Any, Dict, Optional, Type

from cc.base.argument import Argument
from cc.base.arm import Database, Environment, Project, Setting, Version
from cc.base.arm.common.base_entity import _entity_registry
from cc.base.db import get_db_connection
from cc.utils.constants import Constants
from cc.utils.helpers import Helpers
from cc.utils.json_editor import JsonEditor
from cc.utils.logger import setup_logging
from cc.utils.prompter.prompter import Prompter
from cc.utils.shell import exec_sh_command, run_command, set_debug_mode, shell_exit

log = logging.getLogger("CC")


def _show_welcome():
    from cc.utils.console import get_console
    console = get_console()
    console.print()
    console.print("[bold primary]     ██████╗ ██████╗[/]")
    console.print("[bold primary]    ██╔════╝██╔════╝[/]")
    console.print("[bold primary]    ██║     ██║     [/]")
    console.print("[bold primary]    ██║     ██║     [/]")
    console.print("[bold primary]    ╚██████╗╚██████╗[/]")
    console.print("[bold primary]     ╚═════╝ ╚═════╝[/]")
    console.print(f"    [muted]v{Constants.CC_VERSION}[/]")
    console.print()
    console.print("  [bold]Getting started:[/]")
    console.print("    [primary]cc switch[/] PROJECT    Switch to a project")
    console.print("    [primary]cc stat[/]              Show active environment")
    console.print("    [primary]cc setup[/]             First-time configuration")
    console.print()
    console.print("  [bold]Common commands:[/]")
    console.print("    [primary]cc project[/]           Manage projects")
    console.print("    [primary]cc project env list[/]  List environments")
    console.print("    [primary]cc time[/]              Timesheet summary")
    console.print("    [primary]cc config[/]            Settings")
    console.print("    [primary]cc daemon status[/]     Check daemon")
    console.print()
    console.print("  [muted]Run[/] [primary]cc help[/] [muted]or[/] [primary]cc <command> -h[/] [muted]for details.[/]")
    console.print()


class ShellCommandException(Exception): ...


class PythonShellCommandException(ShellCommandException): ...


# Noun-group help blurbs, shown for a bare `cc <group>` invocation.
_GROUP_HELP = {
    "git": "Git & GitHub workflow — branch, fetch, github, pr.",
    "config": "Configure cc — bare `cc config` opens the settings picker.",
    "db": "Databases — create, use, list, drop, init, copy, restore, backup, rename, link, unlink, extend, check.",
    "daemon": "The cc background daemon — start, stop, restart, status, logs.",
    "project": "Projects & environments — create, list, delete, keep, env, cloc, module, open.",
    "rnd": "R&D workspaces — create, consolidate (git worktrees), project, fw (forward-ports).",
    "run": "Run Odoo — start the active environment's server or interactive shell.",
}


class _GroupHandler:
    """Handler for a bare noun-group invocation (e.g. `cc git`) — prints its help."""

    def __init__(self, parser, name):
        self._parser = parser
        self.name = name

    def execute(self):
        self._parser.print_help()
        return True


class CommandMeta(type):
    def __new__(cls, name, bases, dct):
        if "Argument" in dct:
            raise AttributeError(f"{cls} Cannot override 'Argument'.")
        if "Constants" in dct:
            raise AttributeError(f"{cls} Cannot override 'Constants'.")
        if "Helpers" in dct:
            raise AttributeError(f"{cls} Cannot override 'Helpers'.")
        if "JsonEditor" in dct:
            raise AttributeError(f"{cls} Cannot override 'JsonEditor'.")

        dct["Argument"] = Argument
        dct["Constants"] = Constants
        dct["exec_sh_command"] = staticmethod(exec_sh_command)
        dct["run_command"] = staticmethod(run_command)
        dct["Helpers"] = Helpers
        dct["JsonEditor"] = JsonEditor
        return super().__new__(cls, name, bases, dct)


class Command(metaclass=CommandMeta):
    __MAX_INVOKE_COUNT = 5

    _models = {model._name: model for model in _entity_registry}
    __invoke_count = 0

    parser = ArgumentParser(prog="cc", description="cc — a workflow tool for Odoo developers.")
    parser.add_argument("-v", "--version", action="store_true", help="Show the cc version.")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable verbose debug logging to console.")
    subparsers = parser.add_subparsers(dest="command")
    _groups: Dict[str, Any] = {}   # group name -> (group parser, its sub-subparsers)
    prompter = Prompter()

    # === Type Hints === #
    Argument: Type[Argument]
    Constants: Type[Constants]
    Helpers: Type[Helpers]
    database: Type[Database]
    environment: Type[Environment]
    project: Type[Project]
    setting: Type[Setting]
    version: Type[Version]

    def __init__(self, context=False, skip_add_parser=False):
        super().__init__()
        self.conn = None
        self._active_project_cache: Optional[sqlite3.Row] = None
        self._active_environment_cache: Optional[sqlite3.Row] = None
        self._active_version_cache: Optional[sqlite3.Row] = None

        if not hasattr(self, "name"):
            raise AttributeError("Subclasses must define a 'name' attribute.")
        description = (hasattr(self, "description") and self.description) or ""
        if not skip_add_parser:
            # description → shown by `cc <cmd> -h`; help → the one-line blurb
            # listed next to the command in `cc -h` / `cc help`. A `group`
            # attribute nests the command under `cc <group> <name>`.
            group = getattr(self, "group", None)
            if group and self.name == group:
                # group ROOT: bare `cc <group>` runs this command; its flags live
                # on the group parser, alongside the nested subcommands.
                command_parser, _ = Command._ensure_group(group)
                command_parser.set_defaults(handler=self)
                self.add_arguments(command_parser)
            elif group:
                _, subs = Command._ensure_group(group)
                command_parser = subs.add_parser(
                    name=self.name, description=description, help=description or None
                )
                command_parser.set_defaults(handler=self)
                self.add_arguments(command_parser)
            else:
                command_parser = Command.subparsers.add_parser(
                    name=self.name, description=description, help=description or None
                )
                command_parser.set_defaults(handler=self)
                self.add_arguments(command_parser)
            self._parser = command_parser
        self.context = context or {}
        signal.signal(signal.SIGTERM, Command.close_handler)

    @classmethod
    def _ensure_group(cls, group: str):
        """Get-or-create a noun group's ``(parser, subparsers)``.

        Created lazily by the first command that declares ``group = "<name>"``.
        Bare ``cc <group>`` prints help until a group-root command (one whose
        ``name`` equals the group) overrides the handler.
        """
        if group not in Command._groups:
            gp = Command.subparsers.add_parser(
                group,
                help=_GROUP_HELP.get(group, f"{group} commands"),
                description=_GROUP_HELP.get(group),
            )
            gp.set_defaults(handler=_GroupHandler(gp, group))
            Command._groups[group] = (gp, gp.add_subparsers(dest=f"_{group}_sub"))
        return Command._groups[group]

    def __getattr__(self, name: str):
        """
        Dynamically provides access to ORM models and the db connection
        as properties (e.g., self.project, self.db).
        """
        # First, check if the requested attribute is a registered model name.
        if name in self._models:
            return self._models[name]

        # Handle the special case for the 'db' connection.
        if name == "db":
            return get_db_connection()

        # If the attribute is not a model or 'db', raise the standard error.
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def _is_multi_version_mode(self) -> bool:
        setting = self.setting.find_by(name=self.Constants.SETTING_MULTI_VERSION, limit=1)
        return bool(setting and setting.value == "true")

    def _detect_version_from_cwd(self):
        """The registered version whose path is a prefix of the current dir, or None."""
        import os
        try:
            cwd = os.getcwd()
        except (FileNotFoundError, OSError):
            return None
        for version in self.version.find_by():
            if version.path and cwd.startswith(version.path):
                return version
        return None

    @cached_property
    def active_environment(self) -> Environment:
        """The active environment, or None.

        Single-active (default): the one AppState row (last switched), cwd-
        independent. Multi-active (`SETTING_MULTI_VERSION`): the slot for the
        version detected from the current dir, falling back to the most-recently
        switched slot. (Read goes direct per CQRS; mirrors the daemon's
        env._resolve_active_env so CLI and daemon agree.)
        """
        from cc.base.arm.app_state import AppState

        if self._is_multi_version_mode():
            version = self._detect_version_from_cwd()
            if version:
                slot = AppState.search([("version_id", "=", version.id)], limit=1)
                if slot:
                    return slot.environment_id
        state = AppState.search([], orderby="id DESC", limit=1)
        return state.environment_id if state else None

    @cached_property
    def active_project(self) -> Project:
        """
        Derives the active project from the active environment.
        """
        if not self.active_environment:
            return None
        return self.active_environment.project_id

    @cached_property
    def active_version(self):
        """
        Gets the Version object for the active environment.
        This relies on the 'version' relationship in your Environment model.
        """
        if not self.active_environment:
            return None
        return self.active_environment.version_id

    @property
    def active_project_path(self):
        """
        Gets the project path from the active environment.
        This doesn't need its own cache since it relies on active_environment,
        which is already cached.
        """
        if not self.active_environment:
            return None
        return self.active_environment.project_path

    def add_arguments(self, parser):
        for arg in self.arguments():
            arg.add_to_parser(parser)

    def arguments(self):
        """Override this in subclasses to define the list of Argument objects."""
        return []

    def execute(self):
        """Override this in subclasses to define the command handler"""
        raise NotImplementedError

    def get_launch_editor(self) -> Optional[JsonEditor]:
        """
        Finds the launch.json for the active version and returns a JsonEditor instance for it.
        This is now an instance method so it can access self.active_version_path.
        """
        # Use the property that is now correctly part of the Command instance
        active_version = self.active_version
        if not active_version:
            log.error("No active version found. Cannot get launch editor.")
            return None

        # Call the static helper method, passing in the path explicitly
        launch_path_list = Helpers.search_subdir_file(active_version.path, Constants.ODOO_LAUNCH_JSON, True)

        if not launch_path_list:
            log.warning(f"Could not find launch.json within '{active_version.path}'.")
            return None

        return JsonEditor(launch_path_list[0])

    def get_active_project_modules(self) -> tuple[Optional[int], set]:
        """
        Returns a set of active modules for the current environment by reading launch.json.
        This is now an instance method.
        """
        launch_editor = self.get_launch_editor()
        if not launch_editor:
            return None, set()

        launch_args = launch_editor.get(Constants.ODOO_CONFIGURATIONS, Constants.ODOO_ARGS)
        if not launch_args:
            log.warning("Could not find 'args' in launch.json configuration.")
            return None, set()

        update_index = next(
            (
                launch_args.index(arg)
                for arg in [Constants.ODOO_ARG_MODULE_UPDATE, Constants.ODOO_ARG_MODULE_INSTALL]
                if arg in launch_args
            ),
            None,
        )
        if update_index is None or (update_index + 1) >= len(launch_args):
            log.warning("Your launch.json is missing or misconfigured for -u/-i arguments.")
            return None, set()

        modules_arg = launch_args[update_index + 1]
        active_modules = set(modules_arg.split(",")) if modules_arg else set()
        return update_index, active_modules

    def get_active_project_database_from_launch(self) -> tuple[Optional[int], Optional[str]]:
        """
        Returns the active project database *as configured in launch.json*.
        This is now an instance method.
        """
        launch_editor = self.get_launch_editor()
        if not launch_editor:
            return None, None

        launch_args = launch_editor.get(Constants.ODOO_CONFIGURATIONS, Constants.ODOO_ARGS)
        if not launch_args:
            log.warning("Could not find 'args' in launch.json configuration.")
            return None, None

        arg_to_find = Constants.ODOO_ARG_DATABASE
        try:
            db_arg_index = launch_args.index(arg_to_find)
            if (db_arg_index + 1) < len(launch_args):
                active_database = launch_args[db_arg_index + 1]
                return db_arg_index, active_database
        except ValueError:
            pass

        log.warning("Cannot find database arg in launch.json.")
        return None, None

    def project_environment_selector(self, project_id: Project, environment_filter: callable = None) -> Environment:
        if not project_id:
            log.error("No project provided for environment selection.")
            return False

        project_alias = project_id.name
        environments = (
            project_id.environment_ids
            if not environment_filter
            else project_id.environment_ids.filtered(environment_filter)
        )
        if not environments:
            from cc.utils.console import get_console
            console = get_console()
            console.print(f"[error]Project '{project_alias}' has no configured environments.[/]")
            console.print(f"  Run [primary]cc project env create {project_alias}[/] to set one up.")
            return False
        chosen_environment: Optional[Dict[str, Any]] = None
        if len(environments) == 1:
            chosen_environment = environments[0]
            log.debug(f"Project '{project_alias}' has one environment, auto-selecting it.")
        else:
            log.debug(f"Project '{project_alias}' has multiple environments.")
            from cc.utils.prompter.env_selector import EnvSelectorTUI
            from cc.utils.prompter.prompter import PROMPTER_STYLE
            active = self.active_environment
            same_project = active and active.project_id and active.project_id.id == project_id.id
            active_id = active.id if same_project else None
            chosen_environment = EnvSelectorTUI(
                environments=environments,
                project_name=project_alias,
                active_env_id=active_id,
                style=PROMPTER_STYLE,
            ).run()
            if not chosen_environment:
                log.debug("No environment selected.")
                return False

        if not chosen_environment:
            log.error("Error occurred while selecting environment.")
            return False

        return chosen_environment

    def _pick_by_project(self, items):
        """Disambiguate same-named envs across projects via a `project/env` picker.

        `items` are env records or DTOs (need `.name` plus `.project_name` or
        `.project_id.name`). Returns the chosen item, or None if cancelled.
        Env names are intentionally non-unique, so any by-name lookup that finds
        more than one routes through here instead of silently taking the first.
        """
        def _label(it):
            proj = getattr(it, "project_name", None)
            if proj is None:
                pid = getattr(it, "project_id", None)
                proj = pid.name if pid else "?"
            return f"{proj}/{it.name}"

        labels = {_label(it): it for it in items}
        choice = self.prompter.prompt_input_multi(
            sorted(labels), "Multiple environments share that name — choose one"
        )
        return labels.get(choice) if choice else None

    @classmethod
    def invoke(cls, args, context=False):
        Command.__invoke_count += 1
        if Command.__invoke_count > Command.__MAX_INVOKE_COUNT:
            raise RecursionError(f"{cls.name} has been invoked more than {Command.__MAX_INVOKE_COUNT} times")
        command_instance = cls(context=context, skip_add_parser=True)
        group = getattr(cls, "group", None)
        if group and cls.name != group:
            argv = [group, cls.name, *args]
        elif group:  # group root
            argv = [group, *args]
        else:
            argv = [cls.name, *args]
        command_instance.args = cls.parser.parse_args(argv)
        return command_instance.execute()

    def no_args_passed(self):
        """
        Checks if any arguments *specific to this subcommand* were passed
        by comparing them against their default values.
        """
        # Find the parser for this specific subcommand (stashed at registration;
        # grouped commands aren't in the top-level subparsers.choices).
        subcommand_parser = getattr(self, "_parser", None) or Command.subparsers.choices.get(self.name)

        if not subcommand_parser:
            # Fallback for safety (e.g., invoked command)
            log.warning(f"Could not find subparser for '{self.name}'; 'no_args_passed' check may be unreliable.")
            ret = False
            for key, value in vars(self.args).items():
                if key in ["command", "handler"]:
                    continue
                ret = ret or value
            return not ret

        # Get all argument destinations this subcommand's parser knows about
        known_subcommand_args = set()
        for action in subcommand_parser._actions:
            # 'help' is a default action in subparsers, skip it
            if action.dest not in ["help"]:
                known_subcommand_args.add(action.dest)

        log.debug(f"Checking for passed args. Known args for '{self.name}': {known_subcommand_args}")

        # Now, check the values from self.args, but *only* for known args
        for key, value in vars(self.args).items():
            # Only check args that belong to this subcommand
            if key not in known_subcommand_args:
                continue

            # Get the default value for this specific key
            default = subcommand_parser.get_default(key)
            log.debug(f"Checking arg '{key}': value={value!r}, default={default!r}")

            # If the current value is different from the default, an arg was passed
            if value != default:
                log.debug(f"Arg '{key}' was passed (value {value!r} != default {default!r}).")
                return False

        # If loop finishes, no args were different from their defaults
        log.debug("No subcommand args were passed.")
        return True

    def all_args_passed(self):
        ret = True
        for key, value in vars(self.args).items():
            if key in ["command", "handler"]:
                continue
            ret = ret and value
        return ret

    @staticmethod
    def close_handler(signum, frame):
        shell_exit(clean_files=True)

    @classmethod
    def run(cls):
        # Tab-completion is native (see `cc completion`), not argcomplete:
        # `cc` is a shell function wrapping _cc_internal, which argcomplete
        # can't hook, and this call only ever fired under $_ARGCOMPLETE,
        # which was never set — so it was dead. Removed in 3.8.
        # Parse args first to get the global debug flag
        args = cls.parser.parse_args()
        set_debug_mode(args.debug)
        # Call setup_logging *after* parsing args
        # Pass the value of the 'debug' flag to the setup function
        setup_logging(debug_mode=args.debug)

        log.debug(f"Raw arguments parsed: {args}")

        from cc.utils.update_checker import get_notification, trigger_background_check
        trigger_background_check()

        # A command that returns False failed — exit non-zero so scripts and
        # shells (`cc switch X && ...`) can branch on it. None/True → success.
        exit_code = 0
        if hasattr(args, "handler"):
            args.handler.args = args
            if args.handler.execute() is False:
                exit_code = 1
        elif args.version:
            from cc.utils.console import get_console
            get_console().print(f"CC Version: [primary]{cls.Constants.CC_VERSION}[/]")
        else:
            _show_welcome()

        command_name = getattr(getattr(args, "handler", None), "name", None)
        from cc.utils.update_checker import (
            _NOPROMPT,
            _REPO_PATH,
            _git_env,
            clear_update_flag,
            record_prompt,
            should_prompt_user,
        )
        if should_prompt_user(command_name):
            # get_notification() now prints the styled banner itself if an
            # update is pending. We only follow up with the prompt + git pull.
            if get_notification():
                record_prompt()
                from cc.utils.prompter.prompter import Prompter
                if Prompter().prompt_confirm("Update now?"):
                    import subprocess as _sp
                    # Same non-interactive guard as the background fetch — never pop the keychain.
                    _sp.run(["git", "-C", _REPO_PATH, *_NOPROMPT, "pull"], check=False, env=_git_env())
                    clear_update_flag()

        if exit_code:
            import sys
            sys.exit(exit_code)

    @classmethod
    def build_classes(cls):
        classes_dict = cls._get_commands_dict()
        handlers_list = []
        for (group, name), value in classes_dict.items():
            # Bake the resolved name+group into the synthesized handler so the
            # instance reads its own group, not one inherited via the MRO.
            handlers_list.append(type(name, tuple(value[::-1]), {"name": name, "group": group}))

        return handlers_list

    @classmethod
    def _get_commands_dict(cls):
        res = defaultdict(list)

        for command in cls.__subclasses__():

            if "name" in command.__dict__:
                # own-attr name+group (not inherited): a base like ProjectCommand
                # (which extends BranchCommand and has no own name) must not register
                # under its parent's inherited name/group.
                key = (command.__dict__.get("group"), command.__dict__["name"])
                res[key].append(command)

            if command.__subclasses__():
                sub_commands = command._get_commands_dict()
                for key, value in sub_commands.items():
                    res[key].extend(value)
        return res
