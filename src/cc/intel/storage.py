"""
Storage layer for intel — bulk inserts that respect the unique constraints.

The indexer hands these helpers pre-built dicts; we transform them into
ORM creates / upserts. SQLite's `INSERT OR IGNORE` would be faster than
the ORM's per-row create, but for now we stay in-ORM for consistency with
the rest of the codebase.
"""
from __future__ import annotations

import logging

log = logging.getLogger("CC")


def _truncate_csv(files: set | list, max_len: int = 500) -> str:
    """Join files as CSV, truncating at the last comma before max_len."""
    joined = ",".join(sorted(files) if isinstance(files, set) else files)
    if len(joined) <= max_len:
        return joined
    cut = joined[:max_len].rfind(",")
    return joined[:cut] if cut > 0 else joined[:max_len]


def bulk_insert_skill_tags(rows: list[dict]) -> int:
    """
    Insert SkillTag rows, ignoring conflicts on (repository_id, commit_sha, tag).

    Returns the number of rows actually written.
    """
    if not rows:
        return 0

    from cc.base.db import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()

    sql = (
        "INSERT INTO skill_tag "
        "(repository_id, commit_sha, tag, weight, raw_loc, committed_at, top_files) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(repository_id, commit_sha, tag) "
        "DO UPDATE SET top_files = excluded.top_files "
        "WHERE skill_tag.top_files IS NULL"
    )
    params = [
        (r["repository_id"], r["commit_sha"], r["tag"],
         r["weight"], r["raw_loc"], r["committed_at"], r.get("top_files", ""))
        for r in rows
    ]
    cur.executemany(sql, params)
    log.debug(f"storage: processed {len(rows)} skill_tag rows")
    return len(rows)


def upsert_knowledge_index(repository_id: int,
                           accumulators: dict[tuple[str, str], dict]) -> int:
    """
    Merge accumulator dicts into knowledge_index — incrementing counts
    rather than overwriting them.

    accumulators keyed by (symbol, symbol_kind) with values:
        {"symbol", "symbol_kind", "commit_count", "loc", "last_touched", "files"}
    """
    if not accumulators:
        return 0

    from cc.base.db import get_db_connection

    conn = get_db_connection()
    cur = conn.cursor()

    upserted = 0
    for (symbol, kind), acc in accumulators.items():
        files_csv = _truncate_csv(acc["files"])
        cur.execute(
            "SELECT id, commit_count, loc_authored, top_files, last_touched "
            "FROM knowledge_index "
            "WHERE repository_id = ? AND symbol = ? AND symbol_kind = ?",
            (repository_id, symbol, kind),
        )
        existing = cur.fetchone()
        if existing:
            new_count = (existing[1] or 0) + acc["commit_count"]
            new_loc = (existing[2] or 0) + acc["loc"]
            # Merge file lists, dedup, top 5 by string sort
            existing_files = (existing[3] or "").split(",") if existing[3] else []
            merged = sorted(set(filter(None, existing_files + list(acc["files"]))))[:5]
            new_files = ",".join(merged)
            new_last = max(existing[4] or "", acc["last_touched"])
            cur.execute(
                "UPDATE knowledge_index SET "
                "commit_count = ?, loc_authored = ?, top_files = ?, last_touched = ? "
                "WHERE id = ?",
                (new_count, new_loc, new_files, new_last, existing[0]),
            )
        else:
            top5 = _truncate_csv(acc["files"])
            cur.execute(
                "INSERT INTO knowledge_index "
                "(repository_id, symbol, symbol_kind, commit_count, loc_authored, "
                " top_files, last_touched) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (repository_id, symbol, kind, acc["commit_count"], acc["loc"],
                 top5, acc["last_touched"]),
            )
        upserted += 1
    log.debug(f"storage: upserted {upserted} knowledge_index rows for repo {repository_id}")
    return upserted
