"""gh helper tests — PR template discovery (no network, no gh required)."""
import os
import shutil
import subprocess

import pytest

from cc.utils import gh

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
pytestmark = requires_git


def _init(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_find_pr_template_in_github_dir(tmp_path, monkeypatch):
    _init(tmp_path)
    gh_dir = tmp_path / ".github"
    gh_dir.mkdir()
    tmpl = gh_dir / "PULL_REQUEST_TEMPLATE.md"
    tmpl.write_text("## Description\n")
    monkeypatch.chdir(tmp_path)

    found = gh.find_pr_template()
    assert found and os.path.samefile(found, str(tmpl))


def test_find_pr_template_none_when_absent(tmp_path, monkeypatch):
    _init(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert gh.find_pr_template() is None
