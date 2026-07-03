"""
Language packs — pluggable per-language pattern detectors for the indexer.

A LanguagePack inspects a single commit's diff text + file paths, and yields
zero or more (tag, weight, [(symbol, kind), ...]) tuples. Each pack is
independent; multiple packs can fire on the same commit.

Auto-detected per-Repository at indexing time. Adding a pack:

    1. Create `cc/services/intel/languages/<name>.py`
    2. Subclass LanguagePack and implement `detect()` + `tag_diff()`
    3. Add it to `_PACKS` below
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterator, List, Tuple

# Tag yield: (tag, raw_loc_added, [(symbol, kind), ...])
TagTuple = Tuple[str, int, List[Tuple[str, str]]]


class LanguagePack:
    """
    Subclasses must define `name` and `detect`/`tag_diff`.

    `__init__(repo_path)` runs once per indexing pass — packs use it to
    build repo-wide context (e.g. parse Odoo manifests) the per-commit
    `tag_diff` will consult. Defaults to no-op so packs without context
    just work.
    """
    name: str = "base"

    def __init__(self, repo_path=None):
        self.repo_path = repo_path

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        """Return True if this pack should run on this repo."""
        return False

    def tag_diff(self, diff_text: str, file_paths: List[str]) -> Iterator[TagTuple]:
        """Yield (tag, raw_loc, [(symbol, kind), ...]) for one commit."""
        return iter(())


# ---------------------------------------------------------------------------
# Registry + auto-detect
# ---------------------------------------------------------------------------

def detect_packs(repo_path: str) -> list[LanguagePack]:
    """Return every pack whose `detect()` returns True for this repo."""
    from cc.intel.languages.odoo import OdooPack
    from cc.intel.languages.python_generic import PythonGenericPack

    p = Path(repo_path)
    available = [PythonGenericPack, OdooPack]
    return [cls(p) for cls in available if cls.detect(p)]


# ---------------------------------------------------------------------------
# Helpers shared by packs
# ---------------------------------------------------------------------------

def count_added_lines(diff_text: str) -> int:
    """Count `+` lines in a unified diff, excluding the `+++` file headers."""
    n = 0
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            n += 1
    return n


def added_text_only(diff_text: str) -> str:
    """
    Extract just the added lines (without the leading `+`) so regexes don't
    match removed code or context lines as if they were authored.
    """
    out = []
    for line in diff_text.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            out.append(line[1:])
    return "\n".join(out)
