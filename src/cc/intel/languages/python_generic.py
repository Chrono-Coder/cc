"""
Generic Python language pack — patterns that fire on any Python codebase.

These tags are intentionally cross-cutting: they describe *what kind of
work* a commit represents, not framework-specific patterns. See `odoo.py`
for the Odoo-flavored equivalents.

Tags emitted:
    test            tests/ files or TestCase subclasses
    external_api    HTTP/cloud SDK imports
    cli             argparse / click / typer / rich imports
    db_query        sqlite3, psycopg2, sqlalchemy
    async_io        async def / await / asyncio
    concurrency     threading / multiprocessing / concurrent.futures
    dataclass       @dataclass or `from dataclasses`
    regex_heavy     3+ re.* calls in one diff
    security        cryptography / hashlib / secrets / jwt imports
    config_ipc      configuration formats — TOML/YAML/JSON files
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterator, List

from . import LanguagePack, TagTuple, added_text_only


class PythonGenericPack(LanguagePack):
    name = "python_generic"

    @classmethod
    def detect(cls, project_path: Path) -> bool:
        # Any .py anywhere → python pack applies
        return any(project_path.rglob("*.py"))

    # ------------------------------------------------------------------

    _RX_TEST = re.compile(r"\bclass\s+\w+\s*\([^)]*TestCase[^)]*\)")
    _RX_EXTAPI = re.compile(
        r"\bimport\s+(requests|httpx|aiohttp|stripe|boto3|"
        r"paramiko|google\.cloud|azure)|"
        r"\bfrom\s+(requests|httpx|aiohttp|stripe|boto3|"
        r"paramiko|google\.cloud|azure)\b"
    )
    _RX_CLI = re.compile(
        r"\bimport\s+(argparse|click|typer|rich)|"
        r"\bfrom\s+(argparse|click|typer|rich)\b"
    )
    _RX_DB = re.compile(
        r"\bimport\s+(sqlite3|psycopg2|sqlalchemy|pymongo|redis)|"
        r"\bfrom\s+(sqlite3|psycopg2|sqlalchemy|pymongo|redis)\b|"
        r"\.execute\s*\(|\.executemany\s*\("
    )
    _RX_ASYNC = re.compile(r"\basync\s+def\s+\w+|\bawait\s+\w|\basyncio\b")
    _RX_CONCURRENCY = re.compile(
        r"\bimport\s+(threading|multiprocessing|concurrent\.futures)|"
        r"\bfrom\s+(threading|multiprocessing|concurrent\.futures)\b"
    )
    _RX_DATACLASS = re.compile(
        r"@dataclass\b|\bfrom\s+dataclasses\s+import"
    )
    _RX_REGEX = re.compile(r"\bre\.(compile|match|findall|sub|search)\s*\(")
    _RX_SECURITY = re.compile(
        r"\bimport\s+(cryptography|hashlib|secrets|jwt|bcrypt)|"
        r"\bfrom\s+(cryptography|hashlib|secrets|jwt|bcrypt)\b"
    )
    _RX_CLASSDEF = re.compile(r"^class\s+(\w+)\s*\(", re.MULTILINE)
    _RX_DEFNAME = re.compile(r"^def\s+(\w+)\s*\(", re.MULTILINE)

    # ------------------------------------------------------------------

    def tag_diff(self, diff_text: str, file_paths: List[str]) -> Iterator[TagTuple]:
        added = added_text_only(diff_text)
        loc = added.count("\n") + (1 if added and not added.endswith("\n") else 0)

        # ---- File-path tags ----
        if any(_is_test_path(f) for f in file_paths) or self._RX_TEST.search(added):
            yield ("test", loc,
                   [(f, "file") for f in file_paths if f.endswith(".py")][:3])

        # ---- Import-driven tags ----
        for tag, rx in (
            ("external_api",  self._RX_EXTAPI),
            ("cli",           self._RX_CLI),
            ("db_query",      self._RX_DB),
            ("concurrency",   self._RX_CONCURRENCY),
            ("dataclass",     self._RX_DATACLASS),
            ("security",      self._RX_SECURITY),
        ):
            if rx.search(added):
                yield (tag, loc, [])

        if self._RX_ASYNC.search(added):
            yield ("async_io", loc, [])

        if len(self._RX_REGEX.findall(added)) >= 3:
            yield ("regex_heavy", loc, [])

        # ---- Config / IPC files ----
        cfg_files = [f for f in file_paths
                     if f.endswith((".toml", ".yaml", ".yml", ".cfg", ".ini"))]
        if cfg_files:
            yield ("config_ipc", loc,
                   [(f, "file") for f in cfg_files[:3]])

        # NOTE: Bare class/function extraction was here — pulled in phase 0
        # because it produced noisy "symbol-as-tag" rows with mis-attributed
        # LOC. Phase 1 will reintroduce symbol mining attached to specific
        # tags (e.g. capture TestCase subclass names alongside the `test`
        # tag, capture Click command names alongside `cli`).


def _is_test_path(path: str) -> bool:
    p = path.lower()
    return (
        "/tests/" in p or p.startswith("tests/") or
        p.endswith("/test.py") or "/test_" in p or
        os.path.basename(p).startswith("test_")
    )
