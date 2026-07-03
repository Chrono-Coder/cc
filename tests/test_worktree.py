"""
Git-worktree workspace tests (cc.rnd.worktree).

Exercise the real git operations against throwaway repos in tmp_path — no
network, no real DB. Skipped when git isn't installed.
"""
import os
import shutil
import subprocess

import pytest

from cc.rnd import worktree

requires_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not available")
pytestmark = requires_git


def _run(*args):
    subprocess.run(args, check=True, capture_output=True, text=True)


def _make_origin(path):
    _run("git", "init", "-q", "-b", "main", path)
    _run("git", "-C", path, "config", "user.email", "t@t.t")
    _run("git", "-C", path, "config", "user.name", "t")
    # Unique content per origin → distinct root commit, so two unrelated origins
    # don't accidentally share a root SHA (which empty commits in the same second
    # would). Clones of the same origin still share it.
    with open(os.path.join(path, "README"), "w") as f:
        f.write(path)
    _run("git", "-C", path, "add", "README")
    _run("git", "-C", path, "commit", "-q", "-m", "root")


def _clone(origin, dest):
    _run("git", "clone", "-q", origin, dest)
    _run("git", "-C", dest, "config", "user.email", "t@t.t")
    _run("git", "-C", dest, "config", "user.name", "t")


# ── introspection ───────────────────────────────────────────────────────────

def test_root_sha_matches_across_clones(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    a = str(tmp_path / "a"); _clone(o, a)
    b = str(tmp_path / "b"); _clone(o, b)
    assert worktree.root_sha(a) is not None
    assert worktree.root_sha(a) == worktree.root_sha(b)


def test_clone_is_not_linked_worktree(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    a = str(tmp_path / "a"); _clone(o, a)
    assert worktree.is_git_repo(a)
    assert not worktree.is_linked_worktree(a)


# ── create ──────────────────────────────────────────────────────────────────

def test_create_worktrees_adds_present_repos(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    v = str(tmp_path / "v"); os.makedirs(v)
    _clone(o, os.path.join(v, "odoo"))

    target = str(tmp_path / "ws")
    results = worktree.create_worktrees(v, target, "main", repo_names=["odoo", "enterprise"])

    odoo = next(r for r in results if r["repo"] == "odoo")
    assert odoo["ok"], odoo
    assert worktree.is_linked_worktree(os.path.join(target, "odoo"))
    # enterprise wasn't present — simply absent from results
    assert all(r["repo"] != "enterprise" for r in results)


# ── consolidate ─────────────────────────────────────────────────────────────

def test_consolidate_converts_dup_and_keeps_backup(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    canon = str(tmp_path / "canon"); _clone(o, canon)
    dup = str(tmp_path / "dup"); _clone(o, dup)

    # Give the dup a unique branch + commit so preservation is meaningful.
    _run("git", "-C", dup, "checkout", "-q", "-b", "feature-x")
    _run("git", "-C", dup, "commit", "--allow-empty", "-q", "-m", "x")

    res = worktree.consolidate_clone(canon, dup)
    assert res["ok"], res
    assert os.path.isdir(dup + ".cc-bak")          # reversible backup kept
    assert worktree.is_linked_worktree(dup)         # dup is now a worktree
    assert "feature-x" in worktree.local_branches(canon)  # branch preserved


def test_consolidate_rejects_different_repo(tmp_path):
    o1 = str(tmp_path / "o1"); _make_origin(o1)
    o2 = str(tmp_path / "o2"); _make_origin(o2)
    a = str(tmp_path / "a"); _clone(o1, a)
    b = str(tmp_path / "b"); _clone(o2, b)

    res = worktree.consolidate_clone(a, b)
    assert not res["ok"]
    assert "different" in res["error"]
    assert not os.path.exists(b + ".cc-bak")  # nothing touched


def test_consolidate_rejects_dirty_tree(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    a = str(tmp_path / "a"); _clone(o, a)
    b = str(tmp_path / "b"); _clone(o, b)
    with open(os.path.join(b, "dirty.txt"), "w") as f:
        f.write("uncommitted")

    res = worktree.consolidate_clone(a, b)
    assert not res["ok"]
    assert "clean" in res["error"]


# ── planning ────────────────────────────────────────────────────────────────

def test_plan_consolidation_groups_duplicates(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    v1 = str(tmp_path / "v1"); os.makedirs(v1); _clone(o, os.path.join(v1, "odoo"))
    v2 = str(tmp_path / "v2"); os.makedirs(v2); _clone(o, os.path.join(v2, "odoo"))

    groups = worktree.plan_consolidation([v1, v2])
    assert len(groups) == 1
    g = groups[0]
    assert g["repo"] == "odoo"
    assert len(g["dups"]) == 1
    assert g["canonical"]["path"] != g["dups"][0]["path"]


def test_plan_consolidation_ignores_singletons(tmp_path):
    o = str(tmp_path / "o"); _make_origin(o)
    v1 = str(tmp_path / "v1"); os.makedirs(v1); _clone(o, os.path.join(v1, "odoo"))
    assert worktree.plan_consolidation([v1]) == []
