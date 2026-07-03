"""
Git-history indexer.

Walks `git log --all --remotes --no-merges --author=$me` for each Repository,
streams the diff output, runs every applicable LanguagePack over each commit,
and writes SkillTag + KnowledgeIndex rows.

Incremental: keyed on commit SHA. The set of already-indexed SHAs is loaded
once per repo (cheap; one indexed query) and consulted before processing
each commit. First reindex on a 5-year repo: ~30-90s. Subsequent: <1s.

Lock files, generated translations, and minified bundles are excluded via
git pathspec — see `_PATH_EXCLUDES`.
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

from cc.intel.languages import detect_packs
from cc.intel.storage import (bulk_insert_skill_tags,
                                       upsert_knowledge_index)

log = logging.getLogger("CC")


# Per (commit, tag) cap on `weight` so a single huge refactor can't dominate
# rankings. Raw LOC stored separately, uncapped.
DEFAULT_WEIGHT_CAP = 500

# Defer indexing of commits older than this. Configurable via setting.
DEFAULT_LOOKBACK_YEARS = 3

# Pathspec excludes — skip lock files / generated content / vendored libs.
# These don't represent your authored work even when they're huge.
_PATH_EXCLUDES = [
    ":!**/package-lock.json",
    ":!**/poetry.lock",
    ":!**/Pipfile.lock",
    ":!**/yarn.lock",
    ":!**/composer.lock",
    ":!**/Gemfile.lock",
    ":!**/Cargo.lock",
    ":!**/i18n/*.po",
    ":!**/i18n/*.pot",
    ":!**/*.min.js",
    ":!**/*.min.css",
    ":!**/static/lib/**",
    ":!**/vendor/**",
    ":!**/node_modules/**",
    ":!**/.venv/**",
    ":!**/__pycache__/**",
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def index_repository(repo, full: bool = False) -> dict:
    """
    Index one Repository. Returns counters {commits, skill_tags, knowledge}.

    Idempotent: rerunning on the same repo without --full only processes
    commits whose SHAs aren't already in `skill_tag`.
    """
    from cc.base.arm import SkillTag

    me_email = _detect_author_email(repo.path)
    if not me_email:
        log.warning(f"intel: no git user.email at {repo.path} — skipping")
        return {"commits": 0, "skill_tags": 0, "knowledge": 0}

    packs = detect_packs(repo.path)
    if not packs:
        log.debug(f"intel: no language packs match {repo.path}")
        return {"commits": 0, "skill_tags": 0, "knowledge": 0}

    # Load already-indexed SHAs once. For the typical "incremental after
    # last_indexed_at" case this set is small.
    already = set() if full else _existing_shas_for_repo(repo.id)

    log_args = ["--all", "--remotes", "--no-merges", f"--author={me_email}"]
    if not full and repo.last_indexed_at:
        log_args.append(f"--since={repo.last_indexed_at}")
    else:
        log_args.append(f"--since={DEFAULT_LOOKBACK_YEARS}.years.ago")

    counters = {"commits": 0, "skill_tags": 0, "knowledge": 0}
    new_tags: list[dict] = []
    knowledge_acc: dict[tuple[str, str], dict] = {}

    for commit in _stream_commits(repo.path, log_args):
        if commit["sha"] in already:
            continue
        counters["commits"] += 1

        # Run every applicable pack over this commit's diff
        for pack in packs:
            for tag, raw_loc, symbols in pack.tag_diff(commit["diff"], commit["files"]):
                weight = min(raw_loc, DEFAULT_WEIGHT_CAP)
                new_tags.append({
                    "repository_id": repo.id,
                    "commit_sha": commit["sha"],
                    "tag": tag,
                    "weight": weight,
                    "raw_loc": raw_loc,
                    "committed_at": commit["committed_at"],
                    "top_files": ",".join(commit["files"][:10]),
                })
                for sym, kind in symbols:
                    key = (sym, kind)
                    acc = knowledge_acc.setdefault(key, {
                        "symbol": sym, "symbol_kind": kind,
                        "commit_count": 0, "loc": 0,
                        "last_touched": commit["committed_at"],
                        "files": set(),
                    })
                    acc["commit_count"] += 1
                    acc["loc"] += raw_loc
                    if commit["committed_at"] > acc["last_touched"]:
                        acc["last_touched"] = commit["committed_at"]
                    for f in commit["files"][:5]:
                        acc["files"].add(f)

    if full:
        # Wipe knowledge rows before re-inserting — additive upsert would
        # double-count commit_count / loc_authored on repeated --full runs.
        _clear_knowledge_index(repo.id)

    counters["skill_tags"] = bulk_insert_skill_tags(new_tags)
    counters["knowledge"] = upsert_knowledge_index(repo.id, knowledge_acc)

    repo.update({
        "last_indexed_commit_sha": _current_head_sha(repo.path) or "",
        "last_indexed_at": datetime.now(timezone.utc).isoformat(),
    })
    log.info(
        f"intel: indexed {repo.name} — {counters['commits']} commits, "
        f"+{counters['skill_tags']} tags, {counters['knowledge']} symbols"
    )
    return counters


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------

def _detect_author_email(repo_path: str) -> str | None:
    """Resolve `git config user.email` for the repo, or fall back to global."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "config", "user.email"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def _current_head_sha(repo_path: str) -> str | None:
    try:
        r = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except (subprocess.TimeoutExpired, OSError):
        return None


def _clear_knowledge_index(repo_id: int) -> None:
    """Delete all knowledge_index rows for a repo (used before --full rebuild)."""
    from cc.base.db import get_db_connection
    cur = get_db_connection().cursor()
    cur.execute("DELETE FROM knowledge_index WHERE repository_id = ?", (repo_id,))
    log.debug(f"intel: cleared {cur.rowcount} knowledge_index rows for repo {repo_id}")


def _existing_shas_for_repo(repo_id: int) -> set[str]:
    """Pull commit_sha set from skill_tag for incremental dedup."""
    from cc.base.db import get_db_connection
    cur = get_db_connection().cursor()
    cur.execute("SELECT DISTINCT commit_sha FROM skill_tag WHERE repository_id = ?",
                (repo_id,))
    return {row[0] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Commit streaming
# ---------------------------------------------------------------------------

# %H sha, %aI author-date ISO, %s subject. Custom record separator avoids
# subjects containing newlines breaking the parser.
_LOG_FORMAT = "%x1eCC<COMMIT>%H%x1f%aI%x1f%s%x1eCC<DIFF>"


def _stream_commits(repo_path: str, log_args: list[str]):
    """
    Yield {sha, committed_at, subject, files, diff} dicts.

    Uses `git log -p` and parses our custom record markers. Streams stdout
    line-by-line so even repos with 10k commits don't balloon memory.
    """
    cmd = (
        ["git", "-C", repo_path, "log", "-p", "--no-color",
         f"--format={_LOG_FORMAT}"]
        + log_args
        + ["--"]
        + _PATH_EXCLUDES
    )
    log.debug(f"intel git log: {' '.join(cmd[:8])} … (+{len(_PATH_EXCLUDES)} excludes)")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1)
    if proc.stdout is None:
        return

    current = None
    diff_lines: list[str] = []
    file_path_re = re.compile(r"^diff --git a/(\S+) b/\S+$")
    files: list[str] = []

    try:
        for line in proc.stdout:
            if "CC<COMMIT>" in line:
                # Flush previous commit
                if current:
                    current["diff"] = "".join(diff_lines)
                    current["files"] = files
                    yield current
                # Start new commit. Strip leading CC<COMMIT>, parse meta.
                _, _, payload = line.partition("CC<COMMIT>")
                meta_part, _, after = payload.partition("CC<DIFF>")
                meta_fields = meta_part.split("\x1f")
                if len(meta_fields) >= 3:
                    sha, committed_at, subject = (meta_fields[0],
                                                  meta_fields[1],
                                                  meta_fields[2].rstrip("\n"))
                else:
                    sha, committed_at, subject = "", "", ""
                current = {"sha": sha, "committed_at": committed_at,
                           "subject": subject}
                diff_lines = [after] if after else []
                files = []
                continue
            if current is None:
                continue
            m = file_path_re.match(line.rstrip("\n"))
            if m:
                files.append(m.group(1))
            diff_lines.append(line)

        if current:
            current["diff"] = "".join(diff_lines)
            current["files"] = files
            yield current
    finally:
        proc.stdout.close()
        proc.wait(timeout=5)
