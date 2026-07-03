"""
Environment lifecycle (status) tests — set_status + default picker filtering.

Uses the `_db` fixture so no real DB is touched. Covers the anti-bloat rule:
the default switch picker shows active/pinned/recent envs and hides stale
merged/archived ones, while --all (include_all=True) shows everything.
"""
from datetime import datetime, timedelta, timezone

import pytest

from cc.base.db import database_connection_manager
from cc.utils.errors import NotFoundError, ValidationError


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_project():
    from cc.services import environment, project, version
    version.create("17.0", "/opt/v17", branch="17.0")
    proj = project.create("proj")
    pid = proj["id"]

    def mkenv(name):
        dto = environment.create(
            name=name,
            project_id=pid,
            version_name="17.0",
            version_path="/opt/v17",
            project_path="/tmp/p",
            github_url="",
            branch_name=name,
            database_name="db",
            module_names=[],
        )
        return dto["id"]

    return pid, mkenv


def _patch(env_id, **fields):
    """Write fields straight onto the ORM row (bypassing RPC validation)."""
    from cc.base.arm.environment import Environment
    with database_connection_manager():
        Environment.find_by(id=env_id, limit=1).update(fields)


def _iso_days_ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def _names(dtos):
    return {d.name for d in dtos}


# ── set_status ──────────────────────────────────────────────────────────────

def test_set_status_updates_value(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("e1")

    result = environment.set_status(eid, "merged")
    assert result["status"] == "merged"
    assert environment.find_by_name("e1").status == "merged"


def test_set_status_rejects_invalid(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("e1")
    with pytest.raises(ValidationError):
        environment.set_status(eid, "bogus")


def test_set_status_missing_env(_db):
    from cc.services import environment
    _make_project()
    with pytest.raises(NotFoundError):
        environment.set_status(99999, "archived")


# ── default picker filtering ────────────────────────────────────────────────

def test_default_hides_merged_and_archived(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    a, m, ar = mkenv("active"), mkenv("merged"), mkenv("archived")
    environment.set_status(m, "merged")
    environment.set_status(ar, "archived")

    default = environment.find_by_project_name("proj")
    assert _names(default) == {"active"}

    every = environment.find_by_project_name("proj", include_all=True)
    assert _names(every) == {"active", "merged", "archived"}


def test_null_status_counts_as_active(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("legacy")
    _patch(eid, status=None)  # row predating the column

    assert _names(environment.find_by_project_name("proj")) == {"legacy"}


def test_pinned_nonactive_stays_visible(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("merged_but_pinned")
    environment.set_status(eid, "merged")
    _patch(eid, pinned=True)

    assert _names(environment.find_by_project_name("proj")) == {"merged_but_pinned"}


def test_recent_nonactive_stays_visible(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("recently_merged")
    environment.set_status(eid, "merged")
    _patch(eid, last_used_at=_iso_days_ago(1))

    assert _names(environment.find_by_project_name("proj")) == {"recently_merged"}


def test_stale_merged_drops_out(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("long_ago_merged")
    environment.set_status(eid, "merged")
    _patch(eid, last_used_at=_iso_days_ago(60))

    assert environment.find_by_project_name("proj") == []
    assert len(environment.find_by_project_name("proj", include_all=True)) == 1


# ── recent envs picker ──────────────────────────────────────────────────────

def test_get_recent_excludes_archived(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    live, dead = mkenv("live"), mkenv("dead")
    _patch(live, last_used_at=_iso_days_ago(0))
    environment.set_status(dead, "archived")
    _patch(dead, last_used_at=_iso_days_ago(0))

    assert _names(environment.get_recent_envs()) == {"live"}
    assert _names(environment.get_recent_envs(include_all=True)) == {"live", "dead"}


# ── auto-sweep ──────────────────────────────────────────────────────────────

def test_sweep_disabled_is_noop(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("old")
    _patch(eid, last_used_at=_iso_days_ago(60))
    assert environment.sweep_stale(days=0)["swept"] == 0
    assert environment.find_by_name("old").status == "active"


def test_sweep_archives_stale_active(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("old")
    _patch(eid, last_used_at=_iso_days_ago(60))
    assert environment.sweep_stale(days=14) == {"swept": 1, "status": "archived"}
    assert environment.find_by_name("old").status == "archived"


def test_sweep_honors_target_status(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    eid = mkenv("old")
    _patch(eid, last_used_at=_iso_days_ago(60))
    environment.sweep_stale(days=14, status="merged")
    assert environment.find_by_name("old").status == "merged"


def test_sweep_skips_pinned_recent_null_and_nonactive(_db):
    from cc.services import environment
    _, mkenv = _make_project()
    pinned = mkenv("pinned")
    _patch(pinned, last_used_at=_iso_days_ago(60), pinned=True)
    recent = mkenv("recent")
    _patch(recent, last_used_at=_iso_days_ago(1))
    never = mkenv("never")  # last_used_at stays NULL
    already = mkenv("already")
    environment.set_status(already, "merged")
    _patch(already, last_used_at=_iso_days_ago(60))

    assert environment.sweep_stale(days=14)["swept"] == 0
    assert environment.find_by_name("pinned").status == "active"
    assert environment.find_by_name("recent").status == "active"
    assert environment.find_by_name("never").status == "active"
    assert environment.find_by_name("already").status == "merged"


def test_sweep_skips_no_auto_archive_project(_db):
    """A project marked no_auto_archive exempts all its envs from sweeping."""
    from cc.services import environment, project
    pid, mkenv = _make_project()
    eid = mkenv("old")
    _patch(eid, last_used_at=_iso_days_ago(60))

    project.set_auto_archive(pid, True)
    assert environment.sweep_stale(days=14)["swept"] == 0
    assert environment.find_by_name("old").status == "active"

    project.set_auto_archive(pid, False)  # re-include → swept again
    assert environment.sweep_stale(days=14)["swept"] == 1


def test_sweep_reads_settings(_db):
    from cc.base.arm.setting import Setting
    from cc.services import environment
    from cc.utils.constants import Constants
    _, mkenv = _make_project()
    eid = mkenv("old")
    _patch(eid, last_used_at=_iso_days_ago(60))
    with database_connection_manager():
        Setting.create({"name": Constants.SETTING_ENV_AUTO_STALE_DAYS, "value": "30"})
        Setting.create({"name": Constants.SETTING_ENV_AUTO_STALE_STATUS, "value": "merged"})

    assert environment.sweep_stale() == {"swept": 1, "status": "merged"}
    assert environment.find_by_name("old").status == "merged"
