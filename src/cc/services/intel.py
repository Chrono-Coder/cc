"""
Intel — skill telemetry derived from your git history.

RPC namespace `intel.*` exposes:
    scan(roots)              → discover git repos under given paths, register them
    add_repo(path, name?)    → manually register one repo
    list_repos()             → list all registered repos with index state
    reindex(repository_id?, full?)
                             → walk new commits, run language packs, update tables
    reindex_dump(repository_id, limit?)
                             → return raw SkillTag rows for validation

    --- Phase 1: read-side queries ---
    who_knows(symbol)        → rank repos by how much you've touched a symbol
    skills(since?)           → strengths + business-domain breakdown across all repos

The actual crawling lives in `indexer.py`. Language-specific pattern
detection lives under `languages/` as pluggable LanguagePack subclasses.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError, ValidationError

log = logging.getLogger("CC")


def _escape_like(value: str) -> str:
    """Escape SQL LIKE wildcards (% and _) so they match literally."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class RepoInfo:
    id: int
    name: str
    path: str
    origin_url: str
    enabled: bool
    last_indexed_commit_sha: str | None
    last_indexed_at: str | None
    skill_tag_count: int
    knowledge_count: int


@dataclass
class ReindexResult:
    repository_id: int
    repository_name: str
    commits_processed: int
    skill_tags_added: int
    knowledge_updated: int
    elapsed_seconds: float
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_git_repo(path: str) -> bool:
    if not path:
        return False
    p = Path(path)
    return p.is_dir() and (p / ".git").exists()


def _git_origin_url(path: str) -> str:
    """Returns origin URL if configured, else empty string. Never raises."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", path, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=2,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except (subprocess.TimeoutExpired, OSError):
        return ""


def _derive_name(path: str, origin_url: str) -> str:
    """Best-effort name from origin URL, else directory basename."""
    if origin_url:
        # owner/repo from "git@github.com:owner/repo.git" or "https://.../owner/repo"
        for sep in (":", "/"):
            if sep in origin_url:
                tail = origin_url.rsplit(sep, 1)[-1]
                return tail.removesuffix(".git")
    return os.path.basename(os.path.normpath(path))


# ---------------------------------------------------------------------------
# RPC methods
# ---------------------------------------------------------------------------

@rpc_method
def add_repo(path: str, name: str = None) -> dict:
    """
    Register a git repo as a Repository row. Idempotent — re-running on the
    same path returns the existing row.
    """
    from cc.base.arm import Repository
    from cc.base.db import database_connection_manager

    abs_path = str(Path(path).expanduser().resolve())
    if not _is_git_repo(abs_path):
        raise ValidationError(f"Not a git repo: {abs_path}")

    with database_connection_manager():
        existing = Repository.find_by(path=abs_path, limit=1)
        if existing:
            return asdict(_repo_to_info(existing))

        origin_url = _git_origin_url(abs_path)
        repo = Repository.create({
            "name": name or _derive_name(abs_path, origin_url),
            "path": abs_path,
            "origin_url": origin_url,
            "enabled": True,
        })
        log.info(f"intel: registered repo '{repo.name}' at {abs_path}")
        return asdict(_repo_to_info(repo))


@rpc_method
def scan(roots: list = None, max_depth: int = 4) -> list:
    """
    Walk filesystem under `roots`, find git repos, auto-register each one.

    Default roots: paths from cc workspaces. Pass explicit roots (list of
    absolute paths) to scan elsewhere. `max_depth` bounds the walk so we
    don't traverse forever inside huge trees.

    Returns a list of {path, name, registered: bool, already_registered: bool}.
    """
    from cc.base.arm import Repository
    from cc.base.arm.workspace import Workspace
    from cc.base.db import database_connection_manager

    if roots is None:
        with database_connection_manager():
            workspaces = Workspace.search([])
            roots = [w.path for w in workspaces if w.path]
        if not roots:
            roots = [os.path.expanduser("~")]

    results: list[dict] = []
    seen_paths: set[str] = set()
    with database_connection_manager():
        for root in roots:
            root = os.path.expanduser(root)
            if not os.path.isdir(root):
                continue
            for path in _walk_for_git_repos(root, max_depth):
                if path in seen_paths:
                    continue
                seen_paths.add(path)
                existing = Repository.find_by(path=path, limit=1)
                if existing:
                    results.append({
                        "path": path,
                        "name": existing.name,
                        "registered": True,
                        "already_registered": True,
                    })
                    continue
                origin_url = _git_origin_url(path)
                repo = Repository.create({
                    "name": _derive_name(path, origin_url),
                    "path": path,
                    "origin_url": origin_url,
                    "enabled": True,
                })
                results.append({
                    "path": path,
                    "name": repo.name,
                    "registered": True,
                    "already_registered": False,
                })
    log.info(f"intel scan: {len(results)} repos under {roots}")
    return results


@rpc_method
def list_repos() -> list:
    """Return all Repository rows with index state + counts."""
    from cc.base.arm import Repository
    from cc.base.db import database_connection_manager, get_db_connection

    with database_connection_manager():
        repos = Repository.search([])
        # Batch-load counts in two queries instead of 2N
        cur = get_db_connection().cursor()
        cur.execute("SELECT repository_id, COUNT(*) FROM skill_tag GROUP BY repository_id")
        skill_counts = dict(cur.fetchall())
        cur.execute("SELECT repository_id, COUNT(*) FROM knowledge_index GROUP BY repository_id")
        know_counts = dict(cur.fetchall())
        return [
            asdict(_repo_to_info(r,
                                 skill_count=skill_counts.get(r.id, 0),
                                 knowledge_count=know_counts.get(r.id, 0)))
            for r in repos
        ]


@rpc_method
def reindex(repository_id: int = None, full: bool = False) -> list:
    """
    Run the indexer on one repo (by id) or all enabled repos.
    Returns a list of ReindexResult dicts.
    """
    from cc.base.arm import Repository
    from cc.base.db import database_connection_manager
    from cc.intel.indexer import index_repository

    with database_connection_manager():
        if repository_id is not None:
            repo = Repository.search([("id", "=", repository_id)], limit=1)
            if not repo:
                raise NotFoundError(f"Repository id={repository_id} not found")
            repos = [repo]
        else:
            repos = list(Repository.search([("enabled", "=", True)]))

    results: list[dict] = []
    for repo in repos:
        with database_connection_manager():
            # Re-fetch inside this transaction so updates land cleanly
            r = Repository.search([("id", "=", repo.id)], limit=1)
            if not r:
                continue
            t0 = time.perf_counter()
            try:
                stats = index_repository(r, full=full)
                elapsed = time.perf_counter() - t0
                results.append(asdict(ReindexResult(
                    repository_id=r.id,
                    repository_name=r.name,
                    commits_processed=stats["commits"],
                    skill_tags_added=stats["skill_tags"],
                    knowledge_updated=stats["knowledge"],
                    elapsed_seconds=round(elapsed, 2),
                )))
            except Exception as e:
                log.exception(f"intel reindex failed for repo {r.name}")
                results.append(asdict(ReindexResult(
                    repository_id=r.id,
                    repository_name=r.name,
                    commits_processed=0,
                    skill_tags_added=0,
                    knowledge_updated=0,
                    elapsed_seconds=round(time.perf_counter() - t0, 2),
                    error=str(e),
                )))
    return results


@rpc_method
def reindex_dump(repository_id: int, limit: int = 50) -> dict:
    """
    Validation helper: return the raw SkillTag + KnowledgeIndex contents
    for one repository. Used by `cc reindex --dump` to eyeball classifier
    output.
    """
    from cc.base.arm import KnowledgeIndex
    from cc.base.arm import Repository
    from cc.base.arm import SkillTag
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        repo = Repository.search([("id", "=", repository_id)], limit=1)
        if not repo:
            raise NotFoundError(f"Repository id={repository_id} not found")

        tags = SkillTag.search([("repository_id", "=", repo.id)],
                               orderby="committed_at DESC", limit=limit)
        knowledge = KnowledgeIndex.search([("repository_id", "=", repo.id)],
                                          orderby="commit_count DESC", limit=limit)

        # Tag distribution count (raw SQL to avoid loading all rows)
        from cc.base.db import get_db_connection
        cur = get_db_connection().cursor()
        cur.execute(
            "SELECT tag, COUNT(*) FROM skill_tag WHERE repository_id = ? "
            "GROUP BY tag ORDER BY COUNT(*) DESC",
            (repo.id,),
        )
        tag_counts = dict(cur.fetchall())

        return {
            "repository": asdict(_repo_to_info(repo)),
            "tag_distribution": tag_counts,
            "recent_skill_tags": [
                {"commit_sha": t.commit_sha[:8], "tag": t.tag,
                 "weight": t.weight, "raw_loc": t.raw_loc,
                 "committed_at": t.committed_at}
                for t in tags
            ],
            "top_symbols": [
                {"symbol": k.symbol, "kind": k.symbol_kind,
                 "commit_count": k.commit_count, "loc": k.loc_authored,
                 "last_touched": k.last_touched, "files": k.top_files}
                for k in knowledge
            ],
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _walk_for_git_repos(root: str, max_depth: int):
    """Yield absolute paths to git repos under root, capped at max_depth."""
    root_depth = root.rstrip(os.sep).count(os.sep)
    skip_dirs = {"node_modules", ".venv", "venv", "__pycache__",
                 ".tox", ".pytest_cache", "dist", "build", ".idea",
                 # macOS standard home subdirs that never contain code
                 # — keeps the scanner out of TCC-protected app containers.
                 "Library", "Applications", "Music", "Pictures",
                 "Movies", "Public"}
    for dirpath, dirnames, _ in os.walk(root, followlinks=False):
        depth = dirpath.count(os.sep) - root_depth
        if depth > max_depth:
            dirnames[:] = []
            continue
        # Skip noise + hidden dirs except the .git we look for
        dirnames[:] = [d for d in dirnames
                       if d not in skip_dirs and not (d.startswith(".") and d != ".git")]
        if ".git" in dirnames:
            yield dirpath
            dirnames[:] = []  # don't descend into a repo


def _repo_to_info(repo, skill_count: int = None, knowledge_count: int = None) -> RepoInfo:
    from cc.base.db import get_db_connection
    if skill_count is None or knowledge_count is None:
        cur = get_db_connection().cursor()
        cur.execute(
            "SELECT "
            "(SELECT COUNT(*) FROM skill_tag WHERE repository_id = ?), "
            "(SELECT COUNT(*) FROM knowledge_index WHERE repository_id = ?)",
            (repo.id, repo.id),
        )
        skill_count, knowledge_count = cur.fetchone()
    return RepoInfo(
        id=repo.id,
        name=repo.name,
        path=repo.path,
        origin_url=repo.origin_url or "",
        enabled=bool(repo.enabled),
        last_indexed_commit_sha=repo.last_indexed_commit_sha,
        last_indexed_at=repo.last_indexed_at,
        skill_tag_count=skill_count or 0,
        knowledge_count=knowledge_count or 0,
    )


# ---------------------------------------------------------------------------
# Phase 1 — read-side queries
# ---------------------------------------------------------------------------

def _dedupe_files(raw: str | None, cap: int = 10) -> list[str]:
    if not raw:
        return []
    seen: dict[str, None] = {}
    for f in raw.split(","):
        f = f.strip()
        if f and f not in seen:
            seen[f] = None
        if len(seen) >= cap:
            break
    return list(seen)


@rpc_method
def search(query: str, since: str = None, until: str = None,
           limit: int = 20) -> list:
    """
    Unified search across knowledge_index (models, files) and skill_tag (tags).

    Searches both tables with substring matching, merges and deduplicates
    results, sorted by last_touched DESC.
    """
    from cc.base.db import get_db_connection, database_connection_manager

    results: list[dict] = []

    with database_connection_manager():
        cur = get_db_connection().cursor()

        # 1) Search knowledge_index (models, files)
        escaped = _escape_like(query)
        date_clause_k = ""
        k_params: list = [f"%{escaped}%"]
        if since:
            date_clause_k += " AND k.last_touched >= ?"
            k_params.append(since)
        if until:
            date_clause_k += " AND k.last_touched < ?"
            k_params.append(until)
        k_params.append(limit)

        cur.execute(
            f"""
            SELECT r.id, r.name, r.path, r.origin_url,
                   k.symbol, k.symbol_kind, k.commit_count,
                   k.last_touched, k.top_files
            FROM knowledge_index k
            JOIN repository r ON r.id = k.repository_id
            WHERE k.symbol LIKE ? ESCAPE '\\'{date_clause_k}
            ORDER BY k.last_touched DESC, k.commit_count DESC
            LIMIT ?
            """,
            tuple(k_params),
        )
        for row in cur.fetchall():
            results.append({
                "repository_id":   row[0],
                "repository_name": row[1],
                "repository_path": row[2],
                "origin_url":      row[3] or "",
                "match":           row[4],
                "match_kind":      row[5],
                "commit_count":    row[6] or 0,
                "last_touched":    row[7],
                "top_files":       (row[8] or "").split(",") if row[8] else [],
                "last_commit_sha": None,
            })

        # 2) Search skill_tag (tags)
        date_clause_s = ""
        s_params: list = [f"%{escaped}%"]
        if since:
            date_clause_s += " AND s.committed_at >= ?"
            s_params.append(since)
        if until:
            date_clause_s += " AND s.committed_at < ?"
            s_params.append(until)
        s_params.append(limit)

        cur.execute(
            f"""
            SELECT r.id, r.name, r.path, r.origin_url,
                   s.tag,
                   COUNT(DISTINCT s.commit_sha) AS commit_count,
                   MAX(s.committed_at) AS last_touched,
                   GROUP_CONCAT(s.top_files) AS all_files,
                   (SELECT s2.commit_sha FROM skill_tag s2
                    WHERE s2.repository_id = s.repository_id AND s2.tag = s.tag
                    ORDER BY s2.committed_at DESC LIMIT 1) AS last_commit_sha
            FROM skill_tag s
            JOIN repository r ON r.id = s.repository_id
            WHERE s.tag LIKE ? ESCAPE '\\'{date_clause_s}
            GROUP BY r.id, s.tag
            ORDER BY last_touched DESC, commit_count DESC
            LIMIT ?
            """,
            tuple(s_params),
        )
        for row in cur.fetchall():
            results.append({
                "repository_id":   row[0],
                "repository_name": row[1],
                "repository_path": row[2],
                "origin_url":      row[3] or "",
                "match":           row[4],
                "match_kind":      "tag",
                "commit_count":    row[5] or 0,
                "last_touched":    row[6],
                "top_files":       _dedupe_files(row[7]),
                "last_commit_sha": row[8] or None,
            })

    # Merge: sort by last_touched DESC, cap at limit
    results.sort(key=lambda r: r["last_touched"] or "", reverse=True)
    return results[:limit]


@rpc_method
def who_knows(symbol: str, like: bool = False, limit: int = 20) -> list:
    """
    Rank repositories by how much the user has touched a symbol.

    Args:
        symbol: model name ("account.move"), method ("_post"), or file path.
        like:   if True, prefix-match (`account.move` also matches
                `account.move.line` and `account.move.send`).
        limit:  max rows returned.

    Returns: list of dicts with repo metadata + aggregate stats, ranked
    by commit_count DESC.
    """
    from cc.base.db import get_db_connection, database_connection_manager

    with database_connection_manager():
        cur = get_db_connection().cursor()

        if like:
            symbol_clause = "k.symbol LIKE ?"
            symbol_param = symbol + "%"
        else:
            symbol_clause = "k.symbol = ?"
            symbol_param = symbol

        cur.execute(
            f"""
            SELECT r.id, r.name, r.path, r.origin_url,
                   k.symbol, k.symbol_kind, k.commit_count, k.loc_authored,
                   k.last_touched, k.top_files
            FROM knowledge_index k
            JOIN repository r ON r.id = k.repository_id
            WHERE {symbol_clause}
            ORDER BY k.last_touched DESC, k.commit_count DESC
            LIMIT ?
            """,
            (symbol_param, limit),
        )
        rows = cur.fetchall()

    return [
        {
            "repository_id":   row[0],
            "repository_name": row[1],
            "repository_path": row[2],
            "origin_url":      row[3] or "",
            "symbol":          row[4],
            "symbol_kind":     row[5],
            "commit_count":    row[6] or 0,
            "loc_authored":    row[7] or 0,
            "last_touched":    row[8],
            "top_files":       (row[9] or "").split(",") if row[9] else [],
        }
        for row in rows
    ]


@rpc_method
def who_knows_tag(tag: str, like: bool = False, limit: int = 20) -> list:
    """
    Rank repositories by skill tag (e.g. "payroll", "domain_hr_payroll").

    Searches skill_tag table. Substring match by default — "payroll" finds
    "domain_hr_payroll". With like=True, uses prefix match instead.
    """
    from cc.base.db import get_db_connection, database_connection_manager

    with database_connection_manager():
        cur = get_db_connection().cursor()

        escaped = _escape_like(tag)
        if like:
            clause = "s.tag LIKE ? ESCAPE '\\'"
            args = [escaped + "%", limit]
        else:
            clause = "(s.tag = ? OR s.tag LIKE ? ESCAPE '\\')"
            args = [tag, f"%{escaped}%", limit]

        cur.execute(
            f"""
            SELECT r.id, r.name, r.path, r.origin_url,
                   s.tag,
                   COUNT(DISTINCT s.commit_sha) AS commit_count,
                   SUM(s.raw_loc) AS loc_total,
                   MAX(s.committed_at) AS last_touched,
                   GROUP_CONCAT(s.top_files) AS all_files
            FROM skill_tag s
            JOIN repository r ON r.id = s.repository_id
            WHERE {clause}
            GROUP BY r.id, s.tag
            ORDER BY last_touched DESC, commit_count DESC
            LIMIT ?
            """,
            tuple(args),
        )
        rows = cur.fetchall()

    return [
        {
            "repository_id":   row[0],
            "repository_name": row[1],
            "repository_path": row[2],
            "origin_url":      row[3] or "",
            "symbol":          row[4],
            "symbol_kind":     "tag",
            "commit_count":    row[5] or 0,
            "loc_authored":    row[6] or 0,
            "last_touched":    row[7],
            "top_files":       _dedupe_files(row[8]),
        }
        for row in rows
    ]


@rpc_method
def skills(since: str = None, until: str = None,
           repository_id: int = None, top: int = 25) -> dict:
    """
    Aggregate strengths and business-domain breakdown across all (or one)
    repositories.

    Args:
        since:         ISO date — restrict to commits committed at/after this.
        until:         ISO date — restrict to commits committed before this.
        repository_id: scope to one repo if set; else union across all.
        top:           limit on top-tags output.

    Returns: {
        "total_commits":   int,
        "total_repos":     int,
        "top_tags": [{"tag", "commit_count", "repo_count", "weight_total"}, ...],
        "domains": [
            {"parent": "domain_hr", "commits": int, "repos": int,
             "subdomains": [{"tag", "commits", "repos"}, ...]},
            ...
        ],
        "since": str | None,
        "until": str | None,
    }
    """
    from cc.base.db import get_db_connection, database_connection_manager

    where = []
    params = []
    if since:
        where.append("st.committed_at >= ?")
        params.append(since)
    if until:
        where.append("st.committed_at < ?")
        params.append(until)
    if repository_id is not None:
        where.append("st.repository_id = ?")
        params.append(repository_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with database_connection_manager():
        cur = get_db_connection().cursor()

        # Total commits + repos in scope
        cur.execute(
            f"SELECT COUNT(DISTINCT st.commit_sha), COUNT(DISTINCT st.repository_id) "
            f"FROM skill_tag st {where_sql}",
            params,
        )
        total_commits, total_repos = cur.fetchone()
        total_commits = total_commits or 0
        total_repos = total_repos or 0

        # Top tags (excluding domain tags — those have their own section)
        cur.execute(
            f"""
            SELECT st.tag,
                   COUNT(DISTINCT st.commit_sha)    AS commits,
                   COUNT(DISTINCT st.repository_id) AS repos,
                   COALESCE(SUM(st.weight), 0)      AS weight_total
            FROM skill_tag st
            {where_sql}
            {'AND' if where_sql else 'WHERE'} st.tag NOT LIKE 'domain\\_%' ESCAPE '\\'
            GROUP BY st.tag
            ORDER BY commits DESC
            LIMIT ?
            """,
            params + [top],
        )
        top_tags = [
            {"tag": r[0], "commit_count": r[1],
             "repo_count": r[2], "weight_total": r[3]}
            for r in cur.fetchall()
        ]

        # Domain tags — both parent and subdomain. Group sub under parent.
        cur.execute(
            f"""
            SELECT st.tag,
                   COUNT(DISTINCT st.commit_sha)    AS commits,
                   COUNT(DISTINCT st.repository_id) AS repos
            FROM skill_tag st
            {where_sql}
            {'AND' if where_sql else 'WHERE'} st.tag LIKE 'domain\\_%' ESCAPE '\\'
            GROUP BY st.tag
            ORDER BY commits DESC
            """,
            params,
        )
        domain_rows = cur.fetchall()

    domains_by_parent: dict[str, dict] = {}
    for tag, commits, repos in domain_rows:
        parent = _domain_parent(tag)
        if tag == parent:
            entry = domains_by_parent.setdefault(parent,
                {"parent": parent, "commits": 0, "repos": 0, "subdomains": []})
            entry["commits"] = commits
            entry["repos"] = repos
        else:
            entry = domains_by_parent.setdefault(parent,
                {"parent": parent, "commits": 0, "repos": 0, "subdomains": []})
            entry["subdomains"].append({"tag": tag, "commits": commits, "repos": repos})

    # If a parent never had its own row (rare), keep the entry but commits=0.
    domains = sorted(domains_by_parent.values(),
                     key=lambda e: e["commits"], reverse=True)

    return {
        "total_commits": total_commits,
        "total_repos":   total_repos,
        "top_tags":      top_tags,
        "domains":       domains,
        "since":         since,
        "until":         until,
    }


_KNOWN_DOMAIN_PARENTS = {
    "domain_hr", "domain_accounting", "domain_inventory", "domain_mrp",
    "domain_sales", "domain_crm", "domain_pos", "domain_website",
    "domain_purchase", "domain_project", "domain_email", "domain_delivery",
    "domain_payment", "domain_helpdesk", "domain_survey", "domain_event",
    "domain_quality", "domain_documents", "domain_fleet", "domain_loyalty",
    "domain_subscription", "domain_field_service",
}


def _domain_parent(tag: str) -> str:
    """
    'domain_hr_timeoff' → 'domain_hr'
    'domain_accounting_assets' → 'domain_accounting'
    'domain_field_service' → 'domain_field_service'  (itself — it's a parent)
    'domain_pos' → 'domain_pos'
    """
    if tag in _KNOWN_DOMAIN_PARENTS or not tag.startswith("domain_"):
        return tag
    # Walk from longest prefix to shortest to find the parent
    parts = tag.split("_")
    for i in range(len(parts) - 1, 1, -1):
        candidate = "_".join(parts[:i])
        if candidate in _KNOWN_DOMAIN_PARENTS:
            return candidate
    return tag

