"""
R&D creation-flow tests: project.home_repo persistence and the fork-scoped
branch helpers (parse_odoo_remotes, list_fork_branches).
"""
import shutil
import subprocess

import pytest

from cc.base.db import database_connection_manager
from cc.utils.helpers import Helpers


# ── project.home_repo ───────────────────────────────────────────────────────

def test_project_create_stores_home_repo(_db):
    from cc.base.arm.project import Project
    from cc.services import project

    res = project.create("p", home_repo="enterprise")
    assert res["home_repo"] == "enterprise"
    with database_connection_manager():
        assert Project.find_by(name="p", limit=1).home_repo == "enterprise"


def test_project_create_home_repo_defaults_empty(_db):
    from cc.services import project
    assert project.create("p2")["home_repo"] == ""


def test_project_create_stores_main_branch(_db):
    from cc.base.arm.project import Project
    from cc.services import project

    res = project.create("tkt", home_repo="odoo", main_branch="19.0-fix-issue")
    assert res["main_branch"] == "19.0-fix-issue"
    with database_connection_manager():
        assert Project.find_by(name="tkt", limit=1).main_branch == "19.0-fix-issue"


# ── remote parsing (shared helper, also backs switch's _parse_rnd_remotes) ───

def test_parse_odoo_remotes_fork_and_upstream():
    out = (
        "origin\tgit@github.com:odoo-dev/odoo.git (fetch)\n"
        "odoo\tgit@github.com:odoo/odoo.git (fetch)\n"
    )
    assert Helpers.parse_odoo_remotes(out) == ("origin", "odoo")


def test_parse_odoo_remotes_no_fork():
    out = "origin\tgit@github.com:odoo/upgrade.git (fetch)\n"
    assert Helpers.parse_odoo_remotes(out) == (None, "origin")


# ── fork branch listing (needs a real git repo) ─────────────────────────────

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)


@requires_git
def test_list_fork_branches_scopes_to_fork(tmp_path):
    repo = str(tmp_path / "odoo")
    subprocess.run(["git", "init", "-q", repo], check=True)
    _git(repo, "config", "user.email", "t@t.t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "commit", "--allow-empty", "-q", "-m", "init")
    sha = subprocess.run(
        ["git", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()

    # fork remote (odoo-dev) with two tracking refs, plus an upstream we must ignore
    _git(repo, "remote", "add", "origin", "git@github.com:odoo-dev/odoo.git")
    _git(repo, "remote", "add", "odoo", "git@github.com:odoo/odoo.git")
    _git(repo, "update-ref", "refs/remotes/origin/master-feature-x", sha)
    _git(repo, "update-ref", "refs/remotes/origin/19.0-fix-y", sha)
    _git(repo, "update-ref", "refs/remotes/odoo/master", sha)  # upstream — excluded

    assert set(Helpers.list_fork_branches(repo)) == {"master-feature-x", "19.0-fix-y"}


@requires_git
def test_list_fork_branches_empty_without_fork(tmp_path):
    repo = str(tmp_path / "upgrade")
    subprocess.run(["git", "init", "-q", repo], check=True)
    # Only an upstream remote, no odoo-dev fork → nothing to scope to.
    _git(repo, "remote", "add", "origin", "git@github.com:odoo/upgrade.git")
    assert Helpers.list_fork_branches(repo) == []
