"""
Git-worktree helpers for R&D workspaces.

Two operations, both avoiding a re-clone of the (huge) Odoo repos:

* **create** — build a new workspace directory by adding `git worktree`s of each
  shared repo from an existing canonical clone. The worktrees share the source's
  object store, so a second working area for parallel ticket work costs ~nothing.

* **consolidate** — turn duplicate *full* clones of the same repo (the "I cloned
  odoo once per version" situation) into worktrees of a single canonical clone.
  This is **reversible**: the old clone is moved aside to a `<path>.cc-bak`
  sibling (an instant, same-filesystem rename), never deleted — so no data is at
  risk. The user reclaims disk by removing the baks once they're satisfied. Every
  branch in a duplicate is copied into the canonical first, so deleting the bak
  can't lose commits.

All git mutations go through cc.utils.shell.run_command. DB writes (version /
workspace rows) are the caller's responsibility via the daemon RPC layer.
"""
import os

from cc.utils.constants import Constants
from cc.utils.shell import run_command

# Repos cc understands in a shared Odoo checkout.
REPO_NAMES = [
    Constants.ODOO_ODOO,
    Constants.ODOO_ENTERPRISE,
    Constants.ODOO_DESIGN_THEMES,
    Constants.ODOO_UPGRADE,
    Constants.ODOO_UPGRADE_UTIL,
]

_TMP_NS = "refs/remotes/_cc_consolidate"


def _git(path, *args, **kw):
    return run_command(["git", "-C", path, *args], **kw)


# ── repo introspection ──────────────────────────────────────────────────────

def is_git_repo(path):
    return os.path.isdir(path) and _git(path, "rev-parse", "--git-dir").returncode == 0


def is_linked_worktree(path):
    """True if `path` is a linked worktree (.git is a file) rather than a clone."""
    return os.path.isfile(os.path.join(path, ".git"))


def root_sha(path):
    """First root commit — a stable identity for "the same repo"."""
    r = _git(path, "rev-list", "--max-parents=0", "HEAD")
    if r.returncode != 0:
        return None
    shas = r.stdout.split()
    return shas[-1] if shas else None


def working_tree_clean(path):
    r = _git(path, "status", "--porcelain")
    return r.returncode == 0 and not r.stdout.strip()


def current_branch(path):
    """Checked-out branch name, or None if detached."""
    r = _git(path, "symbolic-ref", "--quiet", "--short", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def head_sha(path):
    r = _git(path, "rev-parse", "HEAD")
    return r.stdout.strip() if r.returncode == 0 else None


def local_branches(path):
    r = _git(path, "for-each-ref", "--format=%(refname:short)", "refs/heads/")
    return [b for b in r.stdout.splitlines() if b]


def _ref_exists(path, ref):
    return _git(path, "show-ref", "--verify", "--quiet", ref).returncode == 0


def _is_ancestor(path, maybe_ancestor, descendant):
    return _git(path, "merge-base", "--is-ancestor", maybe_ancestor, descendant).returncode == 0


# ── discovery + planning ────────────────────────────────────────────────────

def discover_clones(version_paths, repo_names=None):
    """Group clones of each repo across the given version paths.

    Returns {repo_name: {root_sha: [info, ...]}} where info is
    {path, version_path, is_worktree, branch, clean}. Linked worktrees are
    included but flagged so the planner won't pick them as canonical.
    """
    repo_names = repo_names or REPO_NAMES
    found = {}
    for vp in version_paths:
        if not vp:
            continue
        for repo in repo_names:
            rp = os.path.join(vp, repo)
            if not is_git_repo(rp):
                continue
            rsha = root_sha(rp)
            if not rsha:
                continue
            found.setdefault(repo, {}).setdefault(rsha, []).append({
                "path": rp,
                "version_path": vp,
                "is_worktree": is_linked_worktree(rp),
                "branch": current_branch(rp),
                "clean": working_tree_clean(rp),
            })
    return found


def plan_consolidation(version_paths, repo_names=None):
    """Work out which duplicate clones can be folded into a canonical one.

    For each (repo, root_sha) group with more than one *full* clone, the first
    clean full clone is the canonical; the other clean full clones become dups to
    convert. Dirty or already-worktree clones are reported as skipped. Returns a
    list of {repo, canonical, dups, skipped:[(info, reason)]}.
    """
    groups = []
    for repo, by_root in discover_clones(version_paths, repo_names).items():
        for _rsha, clones in by_root.items():
            full = [c for c in clones if not c["is_worktree"]]
            if len(full) < 2:
                continue
            canonical = next((c for c in full if c["clean"]), None)
            if not canonical:
                continue
            dups, skipped = [], []
            for c in full:
                if c is canonical:
                    continue
                if not c["clean"]:
                    skipped.append((c, "working tree not clean"))
                else:
                    dups.append(c)
            if dups or skipped:
                groups.append({"repo": repo, "canonical": canonical, "dups": dups, "skipped": skipped})
    return groups


# ── worktree creation ───────────────────────────────────────────────────────

def add_worktree(source_repo, target_path, ref, detach=True):
    """`git worktree add` a repo into target_path at ref. Returns CompletedProcess."""
    args = ["worktree", "add"]
    if detach:
        args.append("--detach")
    args += [target_path, ref]
    return _git(source_repo, *args)


def create_worktrees(source_version_path, target_path, base_branch, repo_names=None):
    """Add a detached worktree of every present repo into target_path.

    Detached at base_branch (the base branch is checked out in the source clone,
    and a branch can only live in one worktree) — `cc switch` later moves each
    onto the ticket branch. Returns a list of per-repo result dicts.
    """
    repo_names = repo_names or REPO_NAMES
    os.makedirs(target_path, exist_ok=True)
    results = []
    for repo in repo_names:
        src = os.path.join(source_version_path, repo)
        if not is_git_repo(src):
            continue
        dest = os.path.join(target_path, repo)
        if os.path.exists(dest):
            results.append({"repo": repo, "ok": False, "error": "target already exists", "path": dest})
            continue
        ref = base_branch or head_sha(src)
        res = add_worktree(src, dest, ref, detach=True)
        results.append({
            "repo": repo,
            "ok": res.returncode == 0,
            "error": None if res.returncode == 0 else res.stderr.strip(),
            "path": dest,
        })
    return results


# ── consolidation ───────────────────────────────────────────────────────────

def _preserve_branches(canonical, dup):
    """Copy every local branch of `dup` into `canonical` (objects + refs).

    So that, once the dup is removed, no commit is orphaned. Fast-forwards where
    safe; preserves divergent branches under a `<branch>__cc` suffix rather than
    overwriting. Returns the list of (original, renamed) preservations.
    """
    _git(canonical, "fetch", "--no-tags", dup, f"+refs/heads/*:{_TMP_NS}/*")
    canonical_head = current_branch(canonical)
    preserved = []
    for b in local_branches(dup):
        dup_tip = _git(dup, "rev-parse", b).stdout.strip()
        if not _ref_exists(canonical, f"refs/heads/{b}"):
            _git(canonical, "branch", b, dup_tip)
            continue
        can_tip = _git(canonical, "rev-parse", b).stdout.strip()
        if can_tip == dup_tip or _is_ancestor(canonical, dup_tip, can_tip):
            continue  # canonical already has these commits
        if _is_ancestor(canonical, can_tip, dup_tip) and b != canonical_head:
            _git(canonical, "branch", "-f", b, dup_tip)  # fast-forward
            continue
        # Divergent (or the branch is canonical's checked-out HEAD) — keep dup's
        # tip under a non-colliding name so nothing is lost.
        safe, i = f"{b}__cc", 1
        while _ref_exists(canonical, f"refs/heads/{safe}"):
            safe, i = f"{b}__cc{i}", i + 1
        _git(canonical, "branch", safe, dup_tip)
        preserved.append((b, safe))
    # Drop the temp namespace (objects stay, referenced by the new branches).
    for ref in _git(canonical, "for-each-ref", "--format=%(refname)", _TMP_NS).stdout.splitlines():
        _git(canonical, "update-ref", "-d", ref)
    return preserved


def consolidate_clone(canonical, dup):
    """Convert full clone `dup` into a worktree of `canonical`. Reversible.

    Returns {ok, backup, ref, detached, preserved, error}. On any git failure the
    moved-aside directory is restored, so the operation is all-or-nothing.
    """
    if root_sha(canonical) != root_sha(dup) or root_sha(canonical) is None:
        return {"ok": False, "error": "different repositories (root commit mismatch)"}
    if is_linked_worktree(dup):
        return {"ok": False, "error": "already a worktree"}
    if not working_tree_clean(dup):
        return {"ok": False, "error": "working tree not clean"}

    branch = current_branch(dup)
    sha = head_sha(dup)
    preserved = _preserve_branches(canonical, dup)

    backup = dup.rstrip(os.sep) + ".cc-bak"
    if os.path.exists(backup):
        return {"ok": False, "error": f"backup path already exists: {backup}"}
    os.rename(dup, backup)

    # A branch checked out in the canonical (e.g. the base) can't be claimed by a
    # second worktree — fall back to detaching at the same commit.
    detached = branch is None or current_branch(canonical) == branch
    if detached:
        res = add_worktree(canonical, dup, sha, detach=True)
    else:
        res = add_worktree(canonical, dup, branch, detach=False)

    if res.returncode != 0:
        os.rename(backup, dup)  # roll back
        return {"ok": False, "error": f"worktree add failed: {res.stderr.strip()}"}
    return {"ok": True, "backup": backup, "ref": branch or sha, "detached": detached, "preserved": preserved}
