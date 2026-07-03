"""
prompt_input_path (3.8): path prompts get Tab-completion (PathCompleter),
~/$VAR expansion, and optional existence validation with retry.

We monkeypatch prompt_toolkit's prompt() to feed controlled input and force
interactive mode, so we exercise the expansion/validation logic without a TTY.
"""
import os

from cc.utils.prompter import prompter as pmod
from cc.utils.prompter.prompter import Prompter


def _force_interactive(monkeypatch):
    monkeypatch.setattr(Prompter, "_is_interactive", staticmethod(lambda *a, **k: True))


def test_expands_home(monkeypatch):
    _force_interactive(monkeypatch)
    monkeypatch.setattr(pmod, "prompt", lambda **k: "~")
    assert Prompter.prompt_input_path("X", kind="any") == os.path.expanduser("~")


def test_expands_env_var(monkeypatch, tmp_path):
    _force_interactive(monkeypatch)
    monkeypatch.setenv("CC_TEST_BASE", str(tmp_path))
    monkeypatch.setattr(pmod, "prompt", lambda **k: "$CC_TEST_BASE")
    assert Prompter.prompt_input_path("X", must_exist=True, kind="dir") == str(tmp_path)


def test_must_exist_rejects_then_accepts(monkeypatch, tmp_path):
    _force_interactive(monkeypatch)
    values = iter(["/no/such/dir/xyz", str(tmp_path)])
    monkeypatch.setattr(pmod, "prompt", lambda **k: next(values))
    assert Prompter.prompt_input_path("X", must_exist=True, kind="dir") == str(tmp_path)


def test_allow_empty_returns_empty(monkeypatch):
    _force_interactive(monkeypatch)
    monkeypatch.setattr(pmod, "prompt", lambda **k: "")
    assert Prompter.prompt_input_path("X", allow_empty=True) == ""


def test_non_interactive_returns_default(monkeypatch):
    monkeypatch.setattr(Prompter, "_is_interactive", staticmethod(lambda *a, **k: False))
    assert Prompter.prompt_input_path("X", default="/tmp") == "/tmp"
