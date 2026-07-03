"""Timesheet reaction to ``switch.before``.

If the previous session ran long, auto-punch at the configured EOD or flag it
and (optionally) prompt — declining raises :class:`EventCancelled` to abort the
switch. Reads go direct to the ORM; the one write (EOD punch-out) routes through
the daemon RPC.
"""

from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from cc.base.arm import SwitchLog
from cc.base.arm.setting import Setting
from cc.daemon.client import call
from cc.events.bus import EventCancelled, subscribe
from cc.events.events import SwitchEvent
from cc.utils.console import get_console
from cc.utils.constants import Constants
from cc.utils.prompter.prompter import Prompter

log = logging.getLogger("CC")


def _setting(name: str) -> str | None:
    row = Setting.find_by(name=name, limit=1)
    return row.value if row and row.value else None


def _threshold_minutes() -> int:
    """Flag threshold in minutes (default 60)."""
    val = _setting(Constants.SETTING_TIMESHEET_THRESHOLD)
    try:
        return int(val) if val else 60
    except (ValueError, TypeError):
        return 60


def _eod() -> time | None:
    val = _setting(Constants.SETTING_TIMESHEET_EOD)
    if not val:
        return None
    try:
        parts = val.strip().split(":")
        return time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        return None


def _auto_eod_punchout(last_dt: datetime) -> bool:
    """Punch out at the session's EOD if it started before EOD and EOD has passed."""
    eod = _eod()
    if not eod:
        return False
    now = datetime.now(timezone.utc).astimezone()
    last_local = last_dt.astimezone()
    eod_dt = last_local.replace(hour=eod.hour, minute=eod.minute, second=0, microsecond=0)
    if last_local >= eod_dt or now <= eod_dt:
        return False
    call("timesheet.eod_punch_out", switched_at=eod_dt.astimezone(timezone.utc).isoformat())
    get_console().print(f"  [muted]Auto-punched out at {eod_dt.strftime('%H:%M')} (EOD)[/]")
    return True


def _print_today_summary() -> None:
    """Print today's switch log as a quick inline summary."""
    # Local midnight (not UTC) so "today" matches the user's calendar day.
    today_start = (
        datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        .astimezone(timezone.utc).isoformat()
    )
    logs = SwitchLog.search([("switched_at", ">=", today_start)], orderby="switched_at ASC")
    if not logs:
        return

    console = get_console()
    threshold = _threshold_minutes()
    console.print()
    console.print("  [primary]Today so far:[/]")
    now = datetime.now(timezone.utc)
    for i, entry in enumerate(logs):
        try:
            if not entry.environment_id:
                continue
            start_dt = datetime.fromisoformat(entry.switched_at).astimezone()
            end_dt = datetime.fromisoformat(logs[i + 1].switched_at).astimezone() if i + 1 < len(logs) else now.astimezone()
            duration = end_dt - start_dt
            h = int(duration.total_seconds() // 3600)
            m = int((duration.total_seconds() % 3600) // 60)
            env_name = entry.environment_id.name if entry.environment_id else "unknown"
            project_name = entry.environment_id.project_id.name if entry.environment_id else "unknown"
            span_minutes = duration.total_seconds() / 60
            flag = "  [error]⚑[/]" if span_minutes > threshold else ""
            end_label = "now " if i + 1 >= len(logs) else end_dt.strftime("%H:%M")
            console.print(
                f"    [muted]{start_dt.strftime('%H:%M')} → {end_label}[/]"
                f"  \\[[bold]{h}h {m:02d}m[/]]"
                f"  {project_name} / {env_name}{flag}"
            )
        except (ValueError, TypeError, IndexError):
            continue
    console.print()


@subscribe("switch.before")
def flag_long_session(event: SwitchEvent) -> None:
    """If the open span exceeds the threshold, auto-punch at EOD or flag + prompt.

    Declining the prompt raises :class:`EventCancelled` → the switch aborts.
    """
    if _setting(Constants.SETTING_TIMESHEET_MODE) == "manual":
        return  # manual mode: switches aren't auto-tracked, nothing to flag

    last = SwitchLog.find_by(orderby="id DESC", limit=1)
    if not last or not last.environment_id:
        return  # no entries, or last entry was a punch-out (cc time --stop)

    try:
        last_dt = datetime.fromisoformat(last.switched_at)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        span_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
    except (ValueError, TypeError):
        return

    if _auto_eod_punchout(last_dt):
        return  # session was auto-closed at EOD, nothing more to flag

    if span_seconds <= _threshold_minutes() * 60:
        return

    span_h = int(span_seconds // 3600)
    span_m = int((span_seconds % 3600) // 60)
    env_name = last.environment_id.name if last.environment_id else "unknown"
    project_name = last.environment_id.project_id.name if last.environment_id else "unknown"

    console = get_console()
    console.print()
    console.print(
        f"  [warning]⏱  {span_h}h {span_m}m on {project_name} / {env_name}[/]"
        f"  [error]\\[flagged][/]"
    )
    _print_today_summary()

    if (_setting(Constants.SETTING_TIMESHEET_PROMPT) or "true").lower() != "false":
        if not Prompter.prompt_confirm("Continue switching?"):
            raise EventCancelled()
