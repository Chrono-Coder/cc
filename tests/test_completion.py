"""
Completion: spec normalization (Argument.complete → source) + the zsh/bash/fish
emitters. Driven by a synthetic spec so we don't touch the class-singleton parser.
"""
import shutil
import subprocess

import pytest

from cc.completion import bash, fish, spec, zsh
from cc.completion.kinds import CompleteKind


class _Act:
    def __init__(self, cc_complete=None, choices=None):
        self.cc_complete = cc_complete
        self.choices = choices


class _Project:
    _name = "project"


class _Database:
    _name = "database"


# ── spec._source normalization ──────────────────────────────────────────

def test_source_entity():
    assert spec._source(_Act(cc_complete=_Project)) == {"type": "entity", "table": "project", "where": ""}


def test_source_database_filters_in_pg():
    src = spec._source(_Act(cc_complete=_Database))
    assert src["table"] == "database" and src["where"] == "WHERE in_pg = 1"


def test_source_values_from_tuple_or_choices():
    assert spec._source(_Act(cc_complete=("a", "b")))["values"] == ["a", "b"]
    assert spec._source(_Act(choices=["x", "y"]))["values"] == ["x", "y"]


def test_source_kinds():
    assert spec._source(_Act(cc_complete=CompleteKind.MODULE)) == {"type": "module"}
    assert spec._source(_Act(cc_complete=CompleteKind.ENV_TARGET)) == {"type": "env_target"}
    assert spec._source(_Act(cc_complete=CompleteKind.COMMAND)) == {"type": "command"}


def test_source_none():
    assert spec._source(_Act()) is None


# ── spec.build recursion + shape helpers ─────────────────────────────────

def _nested_parser():
    """A parser mirroring the grouped CLI: a `db` group with `use`/`drop`
    verbs, plus a flat `switch` command."""
    import argparse
    p = argparse.ArgumentParser(prog="cc")
    sub = p.add_subparsers(dest="command")
    sw = sub.add_parser("switch", help="Switch")
    sw.add_argument("name", nargs="?")
    db = sub.add_parser("db", help="DB group")
    dbsub = db.add_subparsers(dest="_db_sub")
    use = dbsub.add_parser("use", help="Use a DB")
    use.add_argument("name", nargs="?")
    dbsub.add_parser("drop", help="Drop a DB")
    return p


def test_build_recurses_into_groups():
    cmds = spec.build(_nested_parser())
    by = {c["name"]: c for c in cmds}
    assert by["switch"]["subcommands"] == []
    assert [s["name"] for s in by["db"]["subcommands"]] == ["drop", "use"]
    # the nested _SubParsersAction is not leaked as a positional of the group
    assert by["db"]["positionals"] == []


def test_groups_and_leaves():
    cmds = spec.build(_nested_parser())
    assert spec.groups(cmds) == {"db": ["drop", "use"]}
    leaves = {":".join(p): c["name"] for p, c in spec.iter_leaves(cmds)}
    assert leaves == {"switch": "switch", "db:drop": "drop", "db:use": "use"}


# ── emitters ────────────────────────────────────────────────────────────

_SPEC = [
    {"name": "switch", "help": "Switch", "positionals": [
        {"name": "name", "multi": False, "source": {"type": "entity", "table": "project", "where": ""}}],
     "options": [{"names": ["-s", "--silent"], "takes_value": False, "help": "Silent", "source": None},
                 {"names": ["-e", "--env"], "takes_value": True, "help": "Env",
                  "source": {"type": "entity", "table": "environment", "where": ""}}]},
    {"name": "db", "help": "DB", "options": [], "positionals": [
        {"name": "name", "multi": False, "source": {"type": "entity", "table": "database", "where": "WHERE in_pg = 1"}}]},
    {"name": "env", "help": "Env", "options": [], "positionals": [
        {"name": "action", "multi": False, "source": {"type": "values", "values": ["create", "list", "delete"]}},
        {"name": "target", "multi": False, "source": {"type": "env_target"}}]},
    {"name": "help", "help": "Help", "options": [], "positionals": [
        {"name": "topic", "multi": False, "source": {"type": "command"}}]},
]


# A grouped spec: `db` (noun-group, verbs use/drop) + a flat `switch`.
_GROUPED_SPEC = [
    {"name": "switch", "help": "Switch", "options": [], "subcommands": [], "positionals": [
        {"name": "name", "multi": False, "source": {"type": "entity", "table": "project", "where": ""}}]},
    {"name": "db", "help": "DB", "options": [], "positionals": [], "subcommands": [
        {"name": "use", "help": "Use", "options": [], "positionals": [
            {"name": "name", "multi": False, "source": {"type": "entity", "table": "database", "where": "WHERE in_pg = 1"}}]},
        {"name": "drop", "help": "Drop", "options": [
            {"names": ["-y", "--yes"], "takes_value": False, "help": "Yes", "source": None}], "positionals": [
            {"name": "name", "multi": False, "source": {"type": "entity", "table": "database", "where": "WHERE in_pg = 1"}}]},
    ]},
]


def test_zsh_render():
    out = zsh.render(_SPEC, "/tmp/x.db")
    assert "compdef _cc cc" in out
    assert "_cc_ent_database" in out and "WHERE in_pg = 1" in out  # db reads the cache
    assert "_cc_env_target" in out                                  # action-aware
    assert "_cc_cmdnames" in out                                    # help → command names


def test_zsh_render_grouped():
    out = zsh.render(_GROUPED_SPEC, "/tmp/x.db")
    assert "_cc_db_cmds() { compadd use drop }" in out              # verb completer
    assert "_arguments -C '1: :_cc_db_cmds'" in out                 # group peels a level
    assert "_cc_ent_database" in out                                # db use → databases


def test_bash_render():
    out = bash.render(_SPEC, "/tmp/x.db")
    assert "complete -F _cc cc" in out
    assert "WHERE in_pg = 1" in out
    assert "switch:-e)" in out or "switch:--env)" in out           # flag-value case


def test_bash_render_grouped():
    out = bash.render(_GROUPED_SPEC, "/tmp/x.db")
    assert "__cc_is_group" in out
    assert "db) echo \"use drop\"" in out                           # group verb list
    assert "db:use:1)" in out                                       # nested positional key


def test_fish_render():
    out = fish.render(_SPEC, "/tmp/x.db")
    assert "complete -c cc" in out
    assert "__cc_ent_database" in out and "WHERE in_pg = 1" in out


def test_fish_render_grouped():
    out = fish.render(_GROUPED_SPEC, "/tmp/x.db")
    assert "__fish_seen_subcommand_from db; and not __fish_seen_subcommand_from use drop" in out
    assert "__fish_seen_subcommand_from db; and __fish_seen_subcommand_from use" in out


# ── generated scripts must actually parse in their target shell ──────────
# A real `bash -n` / `zsh -n` / `fish --no-execute` catches malformed output
# (e.g. an empty `case … esac`) that string-presence asserts miss. Skips a
# shell that isn't installed so CI on a thin runner stays green.

_SHELLS = [
    ("bash", ["-n"], bash.render),
    ("zsh", ["-n"], zsh.render),
    ("fish", ["--no-execute"], fish.render),
]

# A command with no options AND no positionals — the case most likely to emit a
# degenerate `case … esac` / empty branch.
_EMPTY_SPEC = [{"name": "ping", "help": "no args", "options": [], "positionals": []}]


def _assert_parses(shell, flags, script, tmp_path):
    if not shutil.which(shell):
        pytest.skip(f"{shell} not installed")
    f = tmp_path / f"cc.{shell}"
    f.write_text(script)
    r = subprocess.run([shell, *flags, str(f)], capture_output=True, text=True)
    assert r.returncode == 0, f"{shell} rejected the generated script:\n{r.stderr}"


@pytest.mark.parametrize("shell,flags,render", _SHELLS, ids=[s[0] for s in _SHELLS])
def test_generated_script_parses(shell, flags, render, tmp_path):
    _assert_parses(shell, flags, render(_SPEC, str(tmp_path / "cc.db")), tmp_path)


@pytest.mark.parametrize("shell,flags,render", _SHELLS, ids=[s[0] for s in _SHELLS])
def test_generated_script_parses_with_argless_command(shell, flags, render, tmp_path):
    _assert_parses(shell, flags, render(_EMPTY_SPEC, str(tmp_path / "cc.db")), tmp_path)


@pytest.mark.parametrize("shell,flags,render", _SHELLS, ids=[s[0] for s in _SHELLS])
def test_generated_script_parses_grouped(shell, flags, render, tmp_path):
    # nested `case … esac` / compound `; and` conditions are the parse risk here
    _assert_parses(shell, flags, render(_GROUPED_SPEC, str(tmp_path / "cc.db")), tmp_path)
