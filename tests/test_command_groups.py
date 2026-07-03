"""Noun-group nesting (3.9 consolidation): a command with `group = "git"` is
reached as `cc git <name>`, a bare `cc git` prints group help, flat commands are
untouched, and — critically — an own-attr `group` must NOT leak to subclasses
that merely inherit a grouped command (the project/ hierarchy extends BranchCommand).
"""
import argparse

import pytest

import cc.commands  # noqa: F401 — populate Command.__subclasses__
from cc.base.command import Command, _GroupHandler


def test_group_keying_uses_own_attr_not_inherited():
    # ProjectCommand(BranchCommand) etc. inherit group="git" via the MRO; the
    # registration key must come from each class's OWN __dict__, so switch/open/
    # project/env/stat stay ungrouped while only branch/fetch/github/pr are git.
    # Keyed by (group, name): names are NOT globally unique — e.g. `cc project
    # create` and `cc rnd create` are distinct pairs in the same core.
    pairs = set(Command._get_commands_dict())
    assert ("git", "branch") in pairs
    assert ("git", "pr") in pairs
    assert (None, "switch") in pairs                 # hot-path stays flat
    assert ("project", "open") in pairs              # open/env/cloc/module nest under project
    assert ("project", "env") in pairs
    assert ("project", "cloc") in pairs
    assert ("project", "create") in pairs            # ProjectCommand exploded → create/list/delete
    assert ("rnd", "create") in pairs                # same name, different group — both valid
    assert (None, "project") not in pairs            # base demoted — not a flat command
    assert ("rnd", "project") in pairs                # but `cc rnd project` exists
    # daemon group
    assert ("daemon", "start") in pairs
    assert ("daemon", "logs") in pairs
    # config group: a root (name == group) plus nested members
    assert ("config", "config") in pairs
    assert ("config", "theme") in pairs
    assert ("config", "completion") in pairs
    # db group: exploded kitchen-sink + lifecycle verbs (restore extends CopyCommand
    # but declares its own group, so it stays under db rather than going flat)
    assert ("db", "use") in pairs
    assert ("db", "drop") in pairs
    assert ("db", "restore") in pairs
    assert ("db", "check") in pairs


@pytest.fixture
def fresh_cli(monkeypatch):
    """Fresh parser/subparsers/groups so registration here neither depends on nor
    pollutes the global bootstrap."""
    parser = argparse.ArgumentParser(prog="cc")
    parser.add_argument("-v", "--version", action="store_true")
    parser.add_argument("-d", "--debug", action="store_true")
    monkeypatch.setattr(Command, "parser", parser)
    monkeypatch.setattr(Command, "subparsers", parser.add_subparsers(dest="command"))
    monkeypatch.setattr(Command, "_groups", {})
    return parser


def test_dispatch_routes_group_and_flat(fresh_cli):
    from cc.commands.database.dropdb_command import DropdbCommand
    from cc.commands.git.branch_command import BranchCommand
    from cc.commands.git.fetch_command import FetchCommand

    BranchCommand()
    FetchCommand()
    DropdbCommand()

    assert fresh_cli.parse_args(["git", "branch"]).handler.name == "branch"
    assert fresh_cli.parse_args(["git", "fetch"]).handler.name == "fetch"
    assert fresh_cli.parse_args(["db", "drop", "x"]).handler.name == "drop"


def test_bare_group_is_help_handler(fresh_cli):
    from cc.commands.git.branch_command import BranchCommand
    BranchCommand()
    assert isinstance(fresh_cli.parse_args(["git"]).handler, _GroupHandler)


def test_old_flat_name_is_gone(fresh_cli):
    from cc.commands.git.branch_command import BranchCommand
    BranchCommand()
    with pytest.raises(SystemExit):   # `cc branch` no longer exists (no alias)
        fresh_cli.parse_args(["branch"])


def test_group_root_runs_on_bare_invocation(fresh_cli):
    # ConfigCommand: name == group == "config" → bare `cc config` runs it (the
    # picker), its flags live on the group parser, and members nest under it.
    from cc.commands.system.config_command import ConfigCommand
    from cc.commands.system.theme_command import ThemeCommand
    ConfigCommand()
    ThemeCommand()
    assert fresh_cli.parse_args(["config"]).handler.name == "config"      # bare → root
    assert fresh_cli.parse_args(["config", "-l"]).list is True            # root flag
    assert fresh_cli.parse_args(["config", "theme"]).handler.name == "theme"  # nested
    with pytest.raises(SystemExit):                                       # old flat gone
        fresh_cli.parse_args(["theme"])
