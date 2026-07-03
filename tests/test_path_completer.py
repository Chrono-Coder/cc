"""_PathCompleter expands ``$VAR`` during completion so env-var paths are
navigable. Absolute and ``~`` paths already worked; ``$HOME/...`` used to
complete to nothing. Crucially, the completion offset must stay valid against
the user's RAW ($VAR) text — applying it preserves the prefix and only fills the
basename. Asserted by reconstructing the applied path (format-agnostic across
prompt_toolkit completion styles).
"""
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document

from cc.utils.prompter.prompter import _PathCompleter

_EV = CompleteEvent(completion_requested=True)


def _completed_paths(text, only_dirs=True):
    """Apply each completion to `text`, returning the resulting full strings."""
    c = _PathCompleter(expanduser=True, only_directories=only_dirs)
    out = []
    for comp in c.get_completions(Document(text, len(text)), _EV):
        out.append(text[: len(text) + comp.start_position] + comp.text)
    return out


def test_expands_env_var(tmp_path, monkeypatch):
    (tmp_path / "subdir").mkdir()
    monkeypatch.setenv("CC_TESTROOT", str(tmp_path))
    assert any(p.endswith("/subdir") for p in _completed_paths("$CC_TESTROOT/"))


def test_env_var_partial_basename_keeps_prefix(tmp_path, monkeypatch):
    # The completion applied to the RAW $VAR text must yield $CC_TESTROOT/subdir:
    # the var prefix is preserved, only the basename is completed.
    (tmp_path / "subdir").mkdir()
    monkeypatch.setenv("CC_TESTROOT", str(tmp_path))
    assert "$CC_TESTROOT/subdir" in _completed_paths("$CC_TESTROOT/sub")


def test_absolute_path_still_completes(tmp_path):
    (tmp_path / "subdir").mkdir()
    assert any(p.endswith("/subdir") for p in _completed_paths(str(tmp_path) + "/"))


def test_plain_partial_basename_completes(tmp_path):
    (tmp_path / "subdir").mkdir()
    assert str(tmp_path / "subdir") in _completed_paths(str(tmp_path / "sub"))
