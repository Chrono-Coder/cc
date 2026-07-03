"""
Timesheet service — switch log punch-out and flag management.
"""
import logging

from cc.daemon.rpc_method import rpc_method
from cc.utils.errors import NotFoundError, ValidationError

log = logging.getLogger("CC")


@rpc_method
def punch_out() -> str:
    """
    Create a stop entry in the switch log (no environment_id = punch-out).
    Returns the punch-out timestamp ISO string.
    Raises RuntimeError if already punched out.
    """
    from datetime import datetime, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        last = SwitchLog.find_by(orderby="id DESC", limit=1)
        if last and not last.environment_id:
            raise ValidationError("Already punched out.")
        now = datetime.now(timezone.utc)
        SwitchLog.create({"switched_at": now.isoformat(), "flagged": False})
        log.debug(f"punch_out: created stop entry at {now.isoformat()}")
        return now.isoformat()


@rpc_method
def eod_punch_out(switched_at: str) -> None:
    """Insert an auto-EOD punch-out entry at the given timestamp."""
    from datetime import datetime

    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    datetime.fromisoformat(switched_at)  # validate format
    with database_connection_manager():
        SwitchLog.create({"switched_at": switched_at, "flagged": False})
        log.debug(f"eod_punch_out: created stop entry at {switched_at}")


@rpc_method
def create_entry(env_id: int, started_at: str, ended_at: str = None, note: str = "") -> dict:
    """Create a manual timesheet entry (an explicit span). Overlaps auto/manual
    entries freely; manual entries are authoritative in their window. ended_at
    NULL = an open entry (running until ended). Returns {id}."""
    from datetime import datetime

    from cc.base.arm.environment import Environment
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    datetime.fromisoformat(started_at)  # validate
    if ended_at:
        datetime.fromisoformat(ended_at)
    with database_connection_manager():
        if not Environment.find_by(id=env_id, limit=1):
            raise NotFoundError(f"Environment id={env_id} not found")
        entry = SwitchLog.create({
            "environment_id": env_id,
            "switched_at": started_at,
            "ended_at": ended_at,
            "note": note or None,
            "source": "manual",
            "flagged": False,
        })
        log.debug(f"create_entry: manual id={entry.id} env={env_id} {started_at}..{ended_at}")
        return {"id": entry.id}


@rpc_method
def update_entry(entry_id: int, switched_at: str = None, ended_at: str = None, note: str = None) -> None:
    """Edit a timesheet entry — start (`switched_at`), end (`ended_at`), and/or
    `note`. Only provided fields change. Editing an AUTO entry marks it `edited`,
    promoting it to authoritative (human-touched wins over untouched auto)."""
    from datetime import datetime

    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    if switched_at is not None:
        datetime.fromisoformat(switched_at)  # validate
    if ended_at:
        datetime.fromisoformat(ended_at)
    with database_connection_manager():
        entry = SwitchLog.search([("id", "=", entry_id)], limit=1)
        if not entry:
            raise NotFoundError(f"SwitchLog id={entry_id} not found")
        vals = {}
        if switched_at is not None:
            vals["switched_at"] = switched_at
        if ended_at is not None:
            vals["ended_at"] = ended_at
        if note is not None:
            vals["note"] = note or None
        if vals and (entry.source or "auto") != "manual":
            vals["edited"] = True  # human-touched auto → authoritative
        entry.update(vals)
        log.debug(f"update_entry: id={entry_id} {vals}")


@rpc_method
def delete_entry(entry_id: int) -> None:
    """Delete a switch log entry by id."""
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        entry = SwitchLog.search([("id", "=", entry_id)], limit=1)
        if not entry:
            raise NotFoundError(f"SwitchLog id={entry_id} not found")
        entry._delete()
        log.debug(f"delete_entry: id={entry_id} removed")


@rpc_method
def clear_flags() -> int:
    """
    Clear all flagged switch log entries.
    Returns the number of entries cleared.
    """
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        flagged = SwitchLog.search([("flagged", "=", 1)])
        for entry in flagged:
            entry.update({"flagged": False})
        log.debug(f"clear_flags: cleared {len(flagged)} entries")
        return len(flagged)


def _to_utc(s):
    from datetime import datetime, timezone
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _subtract(seg_s, seg_e, intervals):
    """[seg_s, seg_e] minus the union of `intervals` → list of (start, end)."""
    pieces = [(seg_s, seg_e)]
    for a, b in intervals:
        out = []
        for s, e in pieces:
            if b <= s or a >= e:      # disjoint
                out.append((s, e))
                continue
            if s < a:
                out.append((s, a))     # keep the part before the cut
            if b < e:
                out.append((b, e))     # keep the part after
        pieces = out
    return pieces


@rpc_method
def entries(start: str, end: str) -> list:
    """Resolved timesheet segments overlapping [start, end) — THE shared source
    of truth so the CLI and web render identical totals (no duplicated logic).

    Auto rows (switch-driven, ended_at unset) form a single-threaded gap-based
    baseline. Manual rows and edited-auto rows are explicit, authoritative spans.
    "Human-touched wins": authoritative spans are kept whole; baseline time they
    overlap is carved out, so hours never double-count. Each segment:
    {id, env_id, env_name, start, end, seconds, note, source, edited, authoritative}.
    """
    from datetime import datetime, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.base.db import database_connection_manager

    win_s, win_e = _to_utc(start), _to_utc(end)
    now = datetime.now(timezone.utc)

    with database_connection_manager():
        rows = [r for r in SwitchLog.find_by(orderby="switched_at ASC")
                if _to_utc(r.switched_at) < win_e]

        auto = [r for r in rows if (r.source or "auto") != "manual"]
        manual = [r for r in rows if r.source == "manual"]

        authoritative, baseline = [], []

        # manual rows: explicit, authoritative spans (open → now)
        for r in manual:
            s = _to_utc(r.switched_at)
            e = _to_utc(r.ended_at) if r.ended_at else now
            if e > s:
                authoritative.append((s, e, r))

        # auto rows: gap-based baseline; an edited auto row is authoritative and
        # uses its own end. NULL-env rows are punch-out boundaries (start nothing).
        for i, r in enumerate(auto):
            if not r.environment_id:
                continue  # punch-out: only bounds the previous span
            s = _to_utc(r.switched_at)
            if r.ended_at:
                e = _to_utc(r.ended_at)
            else:
                e = _to_utc(auto[i + 1].switched_at) if i + 1 < len(auto) else now
            if e <= s:
                continue
            if r.edited and r.ended_at:
                authoritative.append((s, e, r))
            else:
                baseline.append((s, e, r))

        auth_intervals = [(s, e) for s, e, _ in authoritative]

        def _emit(s, e, r, is_auth):
            cs, ce = max(s, win_s), min(e, win_e)   # clip to window
            if ce <= cs:
                return None
            env = r.environment_id
            return {
                "id": r.id,
                "env_id": env.id if env else None,
                "env_name": env.name if env else None,
                "start": cs.isoformat(),
                "end": ce.isoformat(),
                "seconds": (ce - cs).total_seconds(),
                "note": r.note or "",
                "source": r.source or "auto",
                "edited": bool(r.edited),
                "flagged": bool(r.flagged),
                "authoritative": is_auth,
            }

        segments = []
        for s, e, r in authoritative:
            seg = _emit(s, e, r, True)
            if seg:
                segments.append(seg)
        # baseline: carve out time covered by any authoritative span
        for s, e, r in baseline:
            for ps, pe in _subtract(s, e, auth_intervals):
                seg = _emit(ps, pe, r, False)
                if seg:
                    segments.append(seg)

        segments.sort(key=lambda x: x["start"])
        return segments
