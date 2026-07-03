"""
Exit-code contract (3.8): a command whose execute() returns False must make
the process exit non-zero, so `cc switch X && ...` and CI scripts can branch on
failure. None / True → exit 0. Pre-3.8 every command exited 0 regardless.

We drive Command.run() directly with a fake parsed-args namespace + handler,
stubbing the heavy startup externals it touches (logging setup, update
checker).
"""
from argparse import Namespace

import pytest

from cc.base.command import Command


def _stub_run_externals(monkeypatch):
    monkeypatch.setattr("cc.base.command.set_debug_mode", lambda *a, **k: None)
    monkeypatch.setattr("cc.base.command.setup_logging", lambda *a, **k: None)
    monkeypatch.setattr("cc.utils.update_checker.trigger_background_check", lambda: None)
    monkeypatch.setattr("cc.utils.update_checker.should_prompt_user", lambda name: False)


class _Handler:
    name = "fake"

    def __init__(self, result):
        self._result = result

    def execute(self):
        return self._result


def _run_with_handler(monkeypatch, result):
    _stub_run_externals(monkeypatch)
    args = Namespace(debug=False, version=False, handler=_Handler(result))
    monkeypatch.setattr(Command.parser, "parse_args", lambda *a, **k: args)
    return Command.run()


def test_false_result_exits_nonzero(monkeypatch):
    with pytest.raises(SystemExit) as exc:
        _run_with_handler(monkeypatch, False)
    assert exc.value.code == 1


def test_none_result_exits_zero(monkeypatch):
    # No SystemExit raised → process falls through to a clean 0 exit.
    _run_with_handler(monkeypatch, None)


def test_true_result_exits_zero(monkeypatch):
    _run_with_handler(monkeypatch, True)
