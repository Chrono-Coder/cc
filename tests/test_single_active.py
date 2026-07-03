"""
Single active environment (3.8): one AppState row, replaced on every switch.
No per-version slots, no freshness expiry — active == the env last switched to,
shown regardless of age (the morning-`cc stat` behavior). Uses the _db fixture.
"""
from datetime import datetime, timedelta, timezone

from cc.base.db import database_connection_manager


def _mk_version(name, path):
    from cc.services import version
    return version.create(name, path, branch=name)["id"]


def _mk_env(name, project_id, version="17.0", path="/opt/v17"):
    from cc.services import environment
    return environment.create(
        name=name, project_id=project_id, version_name=version, version_path=path,
        project_path=f"/tmp/{name}", github_url="", branch_name="main",
        database_name=f"db_{name}", module_names=[],
    )["id"]


def _active_id():
    from cc.services import environment
    with database_connection_manager():
        env = environment._resolve_active_env()
        return env.id if env else None


def _appstate_count():
    from cc.base.arm.app_state import AppState
    with database_connection_manager():
        return len(AppState.find_by())


def _set_last_used(env_id, iso):
    from cc.base.arm.environment import Environment
    with database_connection_manager():
        Environment.find_by(id=env_id, limit=1).update({"last_used_at": iso})


def test_switch_sets_single_active(_db):
    from cc.services import environment, project
    _mk_version("17.0", "/opt/v17")
    p = project.create("proj")
    eid = _mk_env("e1", p["id"])
    environment.switch(eid)
    assert _active_id() == eid
    assert _appstate_count() == 1


def test_old_switch_stays_active(_db):
    """No freshness expiry — a switch from days ago is still the active env."""
    from cc.services import environment, project
    _mk_version("17.0", "/opt/v17")
    p = project.create("proj")
    eid = _mk_env("e1", p["id"])
    environment.switch(eid)
    _set_last_used(eid, (datetime.now(timezone.utc) - timedelta(days=5)).isoformat())
    assert _active_id() == eid  # still active despite age


def test_switch_replaces_active(_db):
    """Switching to a second env collapses to one row pointing at the new env."""
    from cc.services import environment, project
    _mk_version("17.0", "/opt/v17")
    p = project.create("proj")
    e1 = _mk_env("e1", p["id"])
    e2 = _mk_env("e2", p["id"])
    environment.switch(e1)
    environment.switch(e2)
    assert _active_id() == e2
    assert _appstate_count() == 1


def test_multi_active_keeps_per_version_slots(_db):
    """Multi-active (opt-in, SETTING_MULTI_VERSION): switching across versions
    keeps one active slot per version — both stay resumable — and resolution is
    by the caller's version_id."""
    from cc.base.arm.setting import Setting
    from cc.services import environment, project
    from cc.utils.constants import Constants
    with database_connection_manager():
        Setting.create({"name": Constants.SETTING_MULTI_VERSION, "value": "true"})
    v17, v18 = _mk_version("17.0", "/opt/v17"), _mk_version("18.0", "/opt/v18")
    p = project.create("proj")
    e17 = _mk_env("e17", p["id"], version="17.0", path="/opt/v17")
    e18 = _mk_env("e18", p["id"], version="18.0", path="/opt/v18")
    environment.switch(e17)
    environment.switch(e18)
    assert _appstate_count() == 2  # one slot per version
    with database_connection_manager():
        assert environment._resolve_active_env(version_id=v17).id == e17
        assert environment._resolve_active_env(version_id=v18).id == e18
        # no version context → falls back to most-recently switched slot
        assert environment._resolve_active_env().id == e18


def test_multi_active_default_off_is_single(_db):
    """Without the setting, switching across versions stays single-active."""
    from cc.services import environment, project
    _mk_version("17.0", "/opt/v17")
    _mk_version("18.0", "/opt/v18")
    p = project.create("proj")
    e17 = _mk_env("e17", p["id"], version="17.0", path="/opt/v17")
    e18 = _mk_env("e18", p["id"], version="18.0", path="/opt/v18")
    environment.switch(e17)
    environment.switch(e18)
    assert _appstate_count() == 1
    assert _active_id() == e18


def test_get_status_marks_only_active(_db):
    from cc.services import environment, project
    _mk_version("17.0", "/opt/v17")
    p = project.create("proj")
    e1 = _mk_env("e1", p["id"])
    e2 = _mk_env("e2", p["id"])
    environment.switch(e1)
    status = environment.get_status(verbose=True)
    by_id = {e.id: e.is_active for e in status.environments}
    assert by_id[e1] is True
    assert by_id[e2] is False
