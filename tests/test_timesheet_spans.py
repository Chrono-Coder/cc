"""3.11 explicit-span timesheet: manual entries, editing (auto→authoritative),
and the shared `entries()` resolution (human-touched wins, no double-count)."""
from cc.base.db import database_connection_manager
from cc.services import environment, project, timesheet, version

WIN_S, WIN_E = "2026-06-01T09:00:00+00:00", "2026-06-01T12:00:00+00:00"


def _env(name):
    version.upsert("17.0", "/opt/v17", branch="17.0")  # find-or-create
    p = project.create(name + "_p")
    return environment.create(
        name=name, project_id=p["id"], version_name="17.0", version_path="/opt/v17",
        project_path=f"/tmp/{name}", github_url="", branch_name="main",
        database_name=f"db_{name}", module_names=[],
    )["id"]


def _auto(env_id, at):
    """Create an auto (gap-based) switch row at `at`; env_id None = punch-out."""
    from cc.base.arm.switch_log import SwitchLog
    with database_connection_manager():
        return SwitchLog.create({
            "environment_id": env_id, "switched_at": at, "flagged": False, "source": "auto",
        }).id


def _by_env(segs):
    out = {}
    for s in segs:
        out.setdefault(s["env_name"], 0)
        out[s["env_name"]] += s["seconds"]
    return out


def test_auto_baseline_is_gap_based(_db):
    a, b = _env("aa"), _env("bb")
    _auto(a, "2026-06-01T09:00:00+00:00")
    _auto(b, "2026-06-01T11:00:00+00:00")      # bounds a → a = 2h
    _auto(None, "2026-06-01T11:30:00+00:00")    # punch-out bounds b → b = 0.5h

    segs = timesheet.entries(WIN_S, WIN_E)
    totals = _by_env(segs)
    assert totals["aa"] == 7200      # 09:00–11:00
    assert totals["bb"] == 1800      # 11:00–11:30
    assert all(not s["authoritative"] and s["source"] == "auto" for s in segs)


def test_manual_entry_is_authoritative_and_carves_baseline(_db):
    a, b = _env("aa"), _env("bb")
    _auto(a, "2026-06-01T09:00:00+00:00")
    _auto(b, "2026-06-01T11:00:00+00:00")
    _auto(None, "2026-06-01T11:30:00+00:00")
    # manual span inside a's window
    timesheet.create_entry(a, "2026-06-01T10:00:00+00:00", "2026-06-01T10:30:00+00:00", note="ticket X")

    segs = timesheet.entries(WIN_S, WIN_E)
    totals = _by_env(segs)
    # no double-count: a still totals exactly 2h (1h + 0.5h baseline + 0.5h manual)
    assert totals["aa"] == 7200
    auth = [s for s in segs if s["authoritative"]]
    assert len(auth) == 1 and auth[0]["note"] == "ticket X" and auth[0]["source"] == "manual"
    # baseline a is split around the manual span into two pieces
    a_baseline = sorted(s["seconds"] for s in segs
                        if s["env_name"] == "aa" and not s["authoritative"])
    assert a_baseline == [1800.0, 3600.0]   # 10:30–11:00 (0.5h) + 09:00–10:00 (1h)


def test_edit_auto_promotes_to_authoritative(_db):
    a = _env("aa")
    row = _auto(a, "2026-06-01T09:00:00+00:00")
    _auto(None, "2026-06-01T11:00:00+00:00")   # gap end 11:00 → a = 2h baseline
    # edit the auto span: set an explicit end + note → becomes authoritative
    timesheet.update_entry(row, ended_at="2026-06-01T10:45:00+00:00", note="migration")

    segs = timesheet.entries(WIN_S, WIN_E)
    assert len(segs) == 1
    s = segs[0]
    assert s["authoritative"] and s["edited"] and s["source"] == "auto"
    assert s["note"] == "migration" and s["seconds"] == 6300  # 09:00–10:45


def test_manual_mode_switch_creates_no_auto_entry(_db):
    """timesheet.mode=manual: switching logs no auto span (only cc time start/end
    do). Default (auto) still logs one per switch."""
    from cc.base.arm.setting import Setting
    from cc.base.arm.switch_log import SwitchLog
    from cc.utils.constants import Constants

    a = _env("aa")
    with database_connection_manager():
        Setting.create({"name": Constants.SETTING_TIMESHEET_MODE, "value": "manual"})
    environment.switch(a)
    with database_connection_manager():
        assert len(SwitchLog.find_by()) == 0  # no auto row in manual mode
    # a manual entry still records fine
    timesheet.create_entry(a, "2026-06-01T09:00:00+00:00", "2026-06-01T10:00:00+00:00", note="x")
    with database_connection_manager():
        assert len(SwitchLog.find_by()) == 1


def test_edit_manual_does_not_set_edited_flag(_db):
    a = _env("aa")
    eid = timesheet.create_entry(a, "2026-06-01T09:00:00+00:00", "2026-06-01T10:00:00+00:00")["id"]
    timesheet.update_entry(eid, note="added later")
    from cc.base.arm.switch_log import SwitchLog
    with database_connection_manager():
        row = SwitchLog.find_by(id=eid, limit=1)
        assert row.source == "manual" and not row.edited and row.note == "added later"
