"""
Argument.add_to_parser: a positional with nargs="?" must keep its `default`
(regression — dropping it made bare `cc workspace`/`env`/`project` exit 1 by
falling through to print_help). Flags carry their `complete=` as cc_complete.
"""
import argparse

from cc.base.argument import Argument


def test_positional_default_is_honored():
    p = argparse.ArgumentParser()
    Argument(names=["action"], nargs="?", choices=["list", "add"], default="list").add_to_parser(p)
    assert p.parse_args([]).action == "list"


def test_positional_value_overrides_default():
    p = argparse.ArgumentParser()
    Argument(names=["action"], nargs="?", choices=["list", "add"], default="list").add_to_parser(p)
    assert p.parse_args(["add"]).action == "add"


def test_positional_carries_complete():
    p = argparse.ArgumentParser()
    Argument(names=["name"], nargs="?", complete=("a", "b")).add_to_parser(p)
    action = next(a for a in p._actions if a.dest == "name")
    assert action.cc_complete == ("a", "b")


def test_value_flag_carries_complete():
    p = argparse.ArgumentParser()
    Argument(names=["-e", "--env"], default=None, complete=("x", "y")).add_to_parser(p)
    action = next(a for a in p._actions if a.dest == "env")
    assert action.cc_complete == ("x", "y")
    assert p.parse_args([]).env is None


def test_store_true_flag_absent_is_falsy_present_is_true():
    p = argparse.ArgumentParser()
    Argument(names=["-n", "--new"], action="store_true").add_to_parser(p)
    assert not p.parse_args([]).new       # absent → falsy (None here, no explicit default)
    assert p.parse_args(["-n"]).new is True
