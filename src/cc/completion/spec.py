"""Shell-neutral completion spec, built by introspecting the argparse parser;
each emitter (zsh/bash/fish) translates the no-shell-syntax spec."""
import argparse

from cc.completion.kinds import CompleteKind


def _subparsers_action(parser):
    return next(
        (a for a in parser._actions if isinstance(a, argparse._SubParsersAction)),
        None,
    )


def command_names(parser) -> list[str]:
    sub = _subparsers_action(parser)
    return sorted(sub.choices.keys()) if sub else []


def _source(action) -> dict | None:
    """Normalize an action's `cc_complete` (+ argparse choices) to a source."""
    c = getattr(action, "cc_complete", None)
    if c is None:
        if action.choices:
            return {"type": "values", "values": [str(x) for x in action.choices]}
        return None
    if isinstance(c, CompleteKind):
        return {"type": c.value}
    if isinstance(c, (list, tuple)):
        return {"type": "values", "values": [str(x) for x in c]}
    if hasattr(c, "_name"):  # an ORM entity class
        # Only offer DBs currently in Postgres.
        where = "WHERE in_pg = 1" if c._name == "database" else ""
        return {"type": "entity", "table": c._name, "where": where}
    return None


def _command_entry(name: str, subparser, help_text: str) -> dict:
    """One command's normalized spec. Recurses into a noun-group's nested
    subparsers → `subcommands` (empty for a leaf command)."""
    options, positionals, subcommands = [], [], []
    nested = _subparsers_action(subparser)
    for action in subparser._actions:
        if action.dest == "help" or isinstance(action, argparse._SubParsersAction):
            continue
        if action.option_strings:
            takes_value = action.nargs != 0  # store_true/_HelpAction → nargs 0
            options.append({
                "names": list(action.option_strings),
                "takes_value": takes_value,
                "help": action.help or "",
                "source": _source(action) if takes_value else None,
            })
        else:
            positionals.append({
                "name": action.metavar or action.dest,
                "multi": action.nargs in ("*", "+"),
                "source": _source(action),
            })
    if nested:
        help_by = {ca.dest: (ca.help or "") for ca in nested._choices_actions}
        for sub_name, sub_parser in sorted(nested.choices.items()):
            subcommands.append(_command_entry(sub_name, sub_parser, help_by.get(sub_name, "")))
    return {
        "name": name,
        "help": help_text,
        "options": options,
        "positionals": positionals,
        "subcommands": subcommands,
    }


def build(parser) -> list[dict]:
    """[{name, help, options:[...], positionals:[...], subcommands:[...]}] for
    every top-level command.

    option:     {names:[...], takes_value:bool, help:str, source:src|None}
    positional: {name:str, multi:bool, source:src|None}
    subcommand: a nested command entry (same shape) — a noun-group's verbs.
    """
    sub = _subparsers_action(parser)
    if not sub:
        return []
    help_by = {ca.dest: (ca.help or "") for ca in sub._choices_actions}
    return [
        _command_entry(name, subparser, help_by.get(name, ""))
        for name, subparser in sorted(sub.choices.items())
    ]


def iter_all(commands: list[dict]):
    """Yield every command dict, recursing into subcommands (groups first)."""
    for cmd in commands:
        yield cmd
        yield from iter_all(cmd.get("subcommands") or [])


def iter_leaves(commands: list[dict]):
    """Yield (path, cmd) for every executable command — a group expands to its
    verbs (`["db", "use"]`), a flat command stays single (`["switch"]`)."""
    for cmd in commands:
        subs = cmd.get("subcommands") or []
        if subs:
            for path, leaf in iter_leaves(subs):
                yield [cmd["name"], *path], leaf
        else:
            yield [cmd["name"]], cmd


def groups(commands: list[dict]) -> dict[str, list[str]]:
    """Top-level group name → its verb names (only commands that nest)."""
    return {
        cmd["name"]: [s["name"] for s in cmd["subcommands"]]
        for cmd in commands
        if cmd.get("subcommands")
    }


def entity_tables(commands: list[dict]) -> dict[str, str]:
    """Distinct {table: where} across all entity sources (groups included) —
    emitters build one SQLite helper per table."""
    tables = {}
    for cmd in iter_all(commands):
        for item in [*cmd["options"], *cmd["positionals"]]:
            src = item.get("source")
            if src and src.get("type") == "entity":
                tables[src["table"]] = src.get("where", "")
    return tables
