"""
Timesheet helpers (3.8 wave 6): local-day bucketing and a gap-aware total.
Pure logic — no DB or TUI.
"""
from datetime import date, datetime, timedelta

from cc.commands.system.timesheet_command import TimesheetCommand


def test_local_day_bounds_span_exactly_one_day():
    start, end = TimesheetCommand._local_day_bounds(date(2026, 6, 14))
    s = datetime.fromisoformat(start)
    e = datetime.fromisoformat(end)
    assert e - s == timedelta(days=1)
    assert s < e
    # Stored timestamps are UTC, so the query bounds are emitted in UTC.
    assert s.utcoffset() == timedelta(0)


def test_day_total_sums_resolved_segments():
    # _show_day renders resolved segments from timesheet.entries(); the day total
    # is just their sum. (Gap/punch-out/overlap semantics are covered at the
    # service level in test_timesheet_spans.py.)
    segs = [{"seconds": 2 * 3600}, {"seconds": 3600}]
    assert TimesheetCommand._day_total(segs) == 3 * 3600
    assert TimesheetCommand._day_total([]) == 0


def test_hm_format():
    assert TimesheetCommand._hm(3 * 3600 + 5 * 60) == "3h 05m"
    assert TimesheetCommand._hm(0) == "0h 00m"
    assert TimesheetCommand._hm(45 * 60) == "0h 45m"
