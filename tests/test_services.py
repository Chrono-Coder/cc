"""
Service layer tests — use the `db` fixture so no real DB is touched.

Covers: project, environment, database, backup, setting, timesheet services.
Cascade deletes and domain logic are the primary focus.
"""
import pytest
from cc.utils.errors import NotFoundError, ValidationError

from cc.base.db import database_connection_manager


# ── Helpers ──────────────────────────────────────────────────────────────────

def _create_project(name="test_project"):
    from cc.services import project
    return project.create(name)


def _create_env(project_id, name="test_env"):
    from cc.services import environment
    return environment.create(
        name=name,
        project_id=project_id,
        version_name="17.0",
        version_path="/tmp/v17",
        project_path="/tmp/myproject",
        github_url="https://github.com/test/repo",
        branch_name="main",
        database_name="test_db",
        module_names=["sale", "purchase"],
    )


# ── project service ──────────────────────────────────────────────────────────

def test_project_create_returns_id_and_name(_db):
    from cc.services import project
    result = project.create("acme")
    assert result["id"] > 0
    assert result["name"] == "acme"


def test_project_get_all_lists_names(_db):
    from cc.services import project
    project.create("alpha")
    project.create("beta")
    names = project.get_all()
    assert "alpha" in names
    assert "beta" in names


def test_project_delete_removes_project(_db):
    from cc.services import project
    from cc.base.arm.project import Project
    result = project.create("to_delete")
    project.delete(result["id"])
    with database_connection_manager():
        assert not Project.find_by(name="to_delete", limit=1)


def test_project_delete_unknown_raises(_db):
    from cc.services import project
    with pytest.raises(NotFoundError):
        project.delete(99999)


# ── environment service ──────────────────────────────────────────────────────

def test_env_create_returns_dto_dict(_db):
    proj = _create_project()
    result = _create_env(proj["id"])
    assert result["id"] > 0
    assert result["name"] == "test_env"
    assert result["project_name"] == "test_project"
    assert result["database"] == "test_db"


def test_env_create_reuses_existing_version(_db):
    """Creating two envs with same version_name should reuse the Version record."""
    from cc.base.arm.version import Version
    proj = _create_project()
    _create_env(proj["id"], name="env1")
    _create_env(proj["id"], name="env2")
    with database_connection_manager():
        versions = Version.find_by(name="17.0")
    # find_by without limit can return a list or single object; normalise
    if not isinstance(versions, list):
        versions = [versions] if versions else []
    assert len(versions) == 1


def test_env_delete_removes_env_and_cascades(_db):
    """env.delete removes the env + its switch_log, but NOT the DB record.

    The `database` table is a Postgres mirror (database.reconcile) — removing a cc
    env never destroys DB data or its cache row. Dropping a real PG database is
    the explicit cc dropdb / database.drop path.
    """
    from cc.base.arm.environment import Environment
    from cc.base.arm.switch_log import SwitchLog
    from cc.base.arm.database import Database
    from cc.services import environment

    proj = _create_project()
    result = _create_env(proj["id"])
    env_id = result["id"]

    with database_connection_manager():
        env_orm = Environment.search([("id", "=", env_id)], limit=1)
        SwitchLog.create({"environment_id": env_orm.id, "switched_at": "2024-01-01T10:00:00", "flagged": False})

    environment.delete(env_id)

    with database_connection_manager():
        assert not Environment.search([("id", "=", env_id)], limit=1)
        assert not SwitchLog.search([("environment_id", "=", env_id)])
        # DB record is kept (mirror row, owned by reconcile) — env removal != data loss
        assert Database.find_by(name="test_db", limit=1)


def test_env_delete_keeps_db_record_when_shared(_db):
    """Shared database record must NOT be deleted if another env still uses it."""
    from cc.base.arm.database import Database
    from cc.services import environment

    proj = _create_project()
    env1 = _create_env(proj["id"], name="env1")
    # Create env2 pointing to the same database name
    _env2 = environment.create(
        name="env2",
        project_id=proj["id"],
        version_name="17.0",
        version_path="/tmp/v17",
        project_path="/tmp/myproject",
        github_url="",
        branch_name="main",
        database_name="test_db",  # same DB
        module_names=[],
    )

    environment.delete(env1["id"])

    with database_connection_manager():
        assert Database.find_by(name="test_db", limit=1)  # still exists


def test_env_update_changes_field(_db):
    from cc.base.arm.environment import Environment
    from cc.services import environment

    proj = _create_project()
    result = _create_env(proj["id"])
    environment.update(result["id"], name="renamed_env")

    with database_connection_manager():
        env = Environment.search([("id", "=", result["id"])], limit=1)
    assert env.name == "renamed_env"


def test_env_find_by_name_returns_dto_dict(_db):
    from cc.services import environment
    proj = _create_project()
    _create_env(proj["id"])
    result = environment.find_by_name("test_env")
    assert result is not None
    # Must be a DTO (dataclass), not a plain dict at service level
    from cc.services.dto import EnvDetailDTO
    assert isinstance(result, EnvDetailDTO)
    assert result.name == "test_env"


def test_env_find_by_project_name_returns_list(_db):
    from cc.services import environment
    proj = _create_project()
    _create_env(proj["id"], name="env_a")
    _create_env(proj["id"], name="env_b")
    results = environment.find_by_project_name("test_project")
    assert len(results) == 2
    names = {r.name for r in results}
    assert names == {"env_a", "env_b"}


# ── database service ─────────────────────────────────────────────────────────

def test_database_create_returns_id(_db):
    from cc.services import database
    db_id = database.create("mydb")
    assert isinstance(db_id, int)
    assert db_id > 0


def test_database_link_to_env_creates_and_links(_db):
    from cc.base.arm.environment import Environment
    from cc.services import database

    proj = _create_project()
    env_result = _create_env(proj["id"])

    database.link_to_env(env_result["id"], "newdb")

    with database_connection_manager():
        env = Environment.search([("id", "=", env_result["id"])], limit=1)
        db_name = env.database_id.name  # traverse relation inside context
    assert db_name == "newdb"


def test_database_update_renames_record(_db):
    from cc.base.arm.database import Database
    from cc.services import database

    db_id = database.create("original")
    database.update(db_id, name="renamed")

    with database_connection_manager():
        rec = Database.search([("id", "=", db_id)], limit=1)
    assert rec.name == "renamed"


def test_database_delete_removes_record(_db):
    from cc.base.arm.database import Database
    from cc.services import database

    db_id = database.create("to_drop")
    database.delete(db_id)

    with database_connection_manager():
        assert not Database.search([("id", "=", db_id)], limit=1)


# ── project cascade delete ────────────────────────────────────────────────────

def test_project_delete_cascades_all_envs(_db):
    """Deleting a project must remove all its environments and their switch logs."""
    from cc.base.arm.environment import Environment
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import project

    proj = _create_project()
    env1 = _create_env(proj["id"], name="env1")
    env2 = _create_env(proj["id"], name="env2")

    with database_connection_manager():
        for env_id in [env1["id"], env2["id"]]:
            SwitchLog.create({"environment_id": env_id, "switched_at": "2024-01-01T10:00:00", "flagged": False})

    project.delete(proj["id"])

    with database_connection_manager():
        assert not Environment.search([("project_id", "=", proj["id"])])
        assert not SwitchLog.search([("environment_id", "=", env1["id"])])
        assert not SwitchLog.search([("environment_id", "=", env2["id"])])


# ── backup service ───────────────────────────────────────────────────────────

def test_backup_create_and_delete(_db):
    from cc.base.arm.backup import Backup
    from cc.services import backup

    backup.create(
        name="snap1",
        env_name="test_env",
        db_name="test_db",
        file_path="/tmp/snap1.dump",
        size_bytes=1024,
        created_at="2024-01-01T10:00:00",
        odoo_version="17.0",
    )

    with database_connection_manager():
        rec = Backup.find_by(name="snap1", limit=1)
    assert rec is not None
    assert rec.size_bytes == 1024

    backup.delete(rec.id)

    with database_connection_manager():
        assert not Backup.find_by(name="snap1", limit=1)


# ── setting service ──────────────────────────────────────────────────────────

def test_setting_upsert_creates_then_updates(_db):
    from cc.base.arm.setting import Setting
    from cc.services import setting

    setting.upsert("my_key", "first")
    with database_connection_manager():
        s = Setting.find_by(name="my_key", limit=1)
    assert s.value == "first"

    setting.upsert("my_key", "second")
    with database_connection_manager():
        s = Setting.find_by(name="my_key", limit=1)
    assert s.value == "second"


# ── version service ──────────────────────────────────────────────────────────

def test_version_create_returns_id_and_name(_db):
    from cc.services import version
    result = version.create("17.0", "/opt/v17", branch="17.0")
    assert result["id"] > 0
    assert result["name"] == "17.0"


def test_version_create_without_branch(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    result = version.create("16.0", "/opt/v16")
    with database_connection_manager():
        v = Version.search([("id", "=", result["id"])], limit=1)
    assert v.branch is None or v.branch is False


def test_version_delete_removes_record(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    result = version.create("15.0", "/opt/v15")
    version.delete(result["id"])
    with database_connection_manager():
        assert not Version.search([("id", "=", result["id"])], limit=1)


def test_version_delete_unknown_raises(_db):
    from cc.services import version
    with pytest.raises(NotFoundError):
        version.delete(99999)


def test_version_upsert_creates_new(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    result = version.upsert("14.0", "/opt/v14", branch="14.0")
    assert result["id"] > 0
    with database_connection_manager():
        v = Version.search([("id", "=", result["id"])], limit=1)
    assert v.path == "/opt/v14"


def test_version_upsert_updates_existing(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    version.create("13.0", "/opt/v13-old")
    result = version.upsert("13.0", "/opt/v13-new", branch="13.0")
    with database_connection_manager():
        v = Version.search([("id", "=", result["id"])], limit=1)
    assert v.path == "/opt/v13-new"
    # Only one record should exist
    with database_connection_manager():
        all_v = Version.find_by(name="13.0")
    assert len(all_v) == 1


def test_version_update_port(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    result = version.create("12.0", "/opt/v12")
    version.update_port(result["id"], "8072")
    with database_connection_manager():
        v = Version.search([("id", "=", result["id"])], limit=1)
    assert v.port == "8072"


def test_version_update_generic(_db):
    from cc.services import version
    from cc.base.arm.version import Version
    result = version.create("11.0", "/opt/v11")
    version.update(result["id"], branch="11.0")
    with database_connection_manager():
        v = Version.search([("id", "=", result["id"])], limit=1)
    assert v.branch == "11.0"


# ── environment query services ────────────────────────────────────────────────

def test_get_active_database_returns_db_name(_db):
    from cc.services import environment
    proj = _create_project()
    env = _create_env(proj["id"])
    environment.switch(env["id"])
    assert environment.get_active_database() == "test_db"


def test_get_active_database_returns_none_when_no_state(_db):
    from cc.services import environment
    assert environment.get_active_database() is None


def test_get_addons_path_returns_none_when_no_state(_db):
    from cc.services import environment
    assert environment.get_addons_path() is None


def test_get_addons_path_returns_none_when_dirs_dont_exist(_db):
    """Version path /tmp/v17 has no odoo/addons subdir — returns None."""
    from cc.services import environment
    proj = _create_project()
    env = _create_env(proj["id"])  # version_path="/tmp/v17", project_path="/tmp/myproject"
    environment.switch(env["id"])
    # /tmp/v17/odoo/addons, /tmp/v17/enterprise etc. don't exist → None
    assert environment.get_addons_path() is None


def test_get_status_returns_project_and_active_env(_db):
    from cc.services import environment
    from cc.services.dto import ProjectStatusDTO
    proj = _create_project()
    env = _create_env(proj["id"])
    environment.switch(env["id"])
    result = environment.get_status(verbose=True)
    assert isinstance(result, ProjectStatusDTO)
    assert result.project == "test_project"
    assert len(result.environments) == 1
    assert result.environments[0].name == "test_env"
    assert result.environments[0].is_active is True


def test_get_status_active_only_filters_inactive(_db):
    """Without verbose, only the active env appears in environments list."""
    from cc.services import environment
    proj = _create_project()
    _create_env(proj["id"], name="env_b")
    environment.switch(_create_env(proj["id"], name="env_a")["id"])
    result = environment.get_status(verbose=False)
    assert len(result.environments) == 1
    assert result.environments[0].name == "env_a"


# ── system service ────────────────────────────────────────────────────────────

def test_system_describe_returns_known_methods(_db):
    from cc.daemon.router import dispatch
    schema = dispatch("system.describe", {})
    assert isinstance(schema, dict)
    # spot-check a few expected methods
    assert "env.switch" in schema
    assert "setting.upsert" in schema
    assert "timesheet.punch_out" in schema
    # each entry has params + returns
    entry = schema["env.switch"]
    assert "params" in entry
    assert "returns" in entry
    assert "env_id" in entry["params"]
    # semantic enrichment from ORM field names
    assert schema["timesheet.eod_punch_out"]["params"]["switched_at"]["semantic"] == "datetime"
    assert schema["backup.create"]["params"]["file_path"]["semantic"] == "path"
    assert schema["backup.create"]["params"]["note"]["semantic"] == "text"


def test_system_describe_models_returns_environment_schema(_db):
    from cc.daemon.router import dispatch
    schema = dispatch("system.describe_models", {})
    assert isinstance(schema, dict)
    assert "environment" in schema
    env_fields = schema["environment"]["fields"]
    # semantic hints present
    assert env_fields["last_used_at"]["semantic"] == "datetime"
    assert env_fields["github_url"]["semantic"] == "url"
    assert env_fields["notes"]["semantic"] == "text"
    assert env_fields["ticket_ids"]["semantic"] == "csv"
    # relation fields
    assert env_fields["project_id"]["type"] == "many2one"
    assert env_fields["module_ids"]["type"] == "one2many"


# ── timesheet service ─────────────────────────────────────────────────────────

def test_timesheet_eod_punch_out_creates_entry(_db):
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet

    timesheet.eod_punch_out("2024-01-01T17:00:00")

    with database_connection_manager():
        entries = SwitchLog.search([("switched_at", "=", "2024-01-01T17:00:00")])
    assert len(entries) == 1
    assert not entries[0].environment_id  # punch-out has no env


def test_timesheet_punch_out_raises_when_already_out(_db):
    from cc.services import timesheet

    timesheet.punch_out()
    with pytest.raises(ValidationError):
        timesheet.punch_out()


def test_timesheet_punch_out_creates_stop_entry(_db):
    """punch_out inserts a SwitchLog row with no environment_id and returns ISO ts."""
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet

    ts = timesheet.punch_out()

    assert ts  # non-empty string
    with database_connection_manager():
        entries = SwitchLog.search([("switched_at", "=", ts)])
    assert len(entries) == 1
    assert not entries[0].environment_id


def test_timesheet_punch_out_allowed_after_switch(_db):
    """Punching out after a switch (env entry) must succeed — last entry has env_id."""
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet, environment

    proj = _create_project()
    env = _create_env(proj["id"])
    environment.switch(env["id"])  # inserts env-linked entry

    ts = timesheet.punch_out()  # must not raise

    with database_connection_manager():
        stop = SwitchLog.search([("switched_at", "=", ts)])
    assert len(stop) == 1
    assert not stop[0].environment_id


def test_timesheet_clear_flags_resets_all_flagged(_db):
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet

    with database_connection_manager():
        SwitchLog.create({"switched_at": "2024-01-01T09:00:00", "flagged": True})
        SwitchLog.create({"switched_at": "2024-01-01T10:00:00", "flagged": True})
        SwitchLog.create({"switched_at": "2024-01-01T11:00:00", "flagged": False})

    count = timesheet.clear_flags()

    assert count == 2
    with database_connection_manager():
        still_flagged = SwitchLog.search([("flagged", "=", 1)])
    assert len(still_flagged) == 0


# ── environment.switch ────────────────────────────────────────────────────────

def test_switch_creates_log_entry(_db):
    """switch() must write a SwitchLog entry for the switched-to env."""
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment

    proj = _create_project()
    env = _create_env(proj["id"])
    environment.switch(env["id"])

    with database_connection_manager():
        entries = SwitchLog.search([("environment_id", "=", env["id"])])
    assert len(entries) == 1


def test_switch_returns_dto(_db):
    """switch() must return a SwitchResultDTO with correct fields."""
    from cc.services import environment
    from cc.services.dto import SwitchResultDTO

    proj = _create_project()
    env = _create_env(proj["id"])
    result = environment.switch(env["id"])

    assert isinstance(result, SwitchResultDTO)
    assert result.env_id == env["id"]
    assert result.env_name == "test_env"
    assert result.project_name == "test_project"
    assert result.database == "test_db"


def test_switch_raises_on_unknown_env(_db):
    from cc.services import environment
    with pytest.raises(NotFoundError):
        environment.switch(99999)


def test_switch_updates_app_state(_db):
    """After switch, get_active_database must return the new env's DB."""
    from cc.services import environment

    proj = _create_project()
    env_a = _create_env(proj["id"], name="env_a")
    env_b = _create_env(proj["id"], name="env_b")

    # Create env_b with a distinct DB
    from cc.base.arm.database import Database
    from cc.base.arm.environment import Environment
    with database_connection_manager():
        db_b = Database.create({"name": "db_b"})
        env_b_orm = Environment.search([("id", "=", env_b["id"])], limit=1)
        env_b_orm.update({"database_id": db_b.id})

    environment.switch(env_b["id"])
    active_db = environment.get_active_database()
    assert active_db == "db_b"


def test_switch_flags_stale_previous_entry(_db):
    """If the last switch was > threshold minutes ago, that entry gets flagged."""
    from datetime import datetime, timedelta, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment

    proj = _create_project()
    env_a = _create_env(proj["id"], name="env_a")
    env_b = _create_env(proj["id"], name="env_b")

    # Insert a stale switch entry (2 hours ago)
    stale_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with database_connection_manager():
        SwitchLog.create({
            "environment_id": env_a["id"],
            "switched_at": stale_ts,
            "flagged": False,
        })

    environment.switch(env_b["id"])

    with database_connection_manager():
        stale_entry = SwitchLog.search([("switched_at", "=", stale_ts)])
    assert len(stale_entry) == 1
    assert stale_entry[0].flagged


def test_switch_does_not_flag_recent_entry(_db):
    """If the last switch was under threshold minutes ago, no flagging occurs."""
    from datetime import datetime, timedelta, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment

    proj = _create_project()
    env_a = _create_env(proj["id"], name="env_a")
    env_b = _create_env(proj["id"], name="env_b")

    # Insert a recent switch entry (5 minutes ago — well under default 60 min threshold)
    recent_ts = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with database_connection_manager():
        SwitchLog.create({
            "environment_id": env_a["id"],
            "switched_at": recent_ts,
            "flagged": False,
        })

    environment.switch(env_b["id"])

    with database_connection_manager():
        entry = SwitchLog.search([("switched_at", "=", recent_ts)])
    assert len(entry) == 1
    assert not entry[0].flagged


def test_switch_respects_custom_threshold(_db):
    """A setting of threshold=1 minute should flag a 5-minute-old entry."""
    from datetime import datetime, timedelta, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment, setting

    setting.upsert("timesheet_flag_threshold", "1")

    proj = _create_project()
    env_a = _create_env(proj["id"], name="env_a")
    env_b = _create_env(proj["id"], name="env_b")

    five_min_ago = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    with database_connection_manager():
        SwitchLog.create({
            "environment_id": env_a["id"],
            "switched_at": five_min_ago,
            "flagged": False,
        })

    environment.switch(env_b["id"])

    with database_connection_manager():
        entry = SwitchLog.search([("switched_at", "=", five_min_ago)])
    assert entry[0].flagged


def test_switch_prunes_old_logs(_db):
    """switch() must delete SwitchLog entries older than 90 days."""
    from datetime import datetime, timedelta, timezone

    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment

    proj = _create_project()
    env = _create_env(proj["id"])

    old_ts = (datetime.now(timezone.utc) - timedelta(days=91)).isoformat()
    with database_connection_manager():
        SwitchLog.create({"environment_id": env["id"], "switched_at": old_ts, "flagged": False})

    environment.switch(env["id"])

    with database_connection_manager():
        old_entries = SwitchLog.search([("switched_at", "=", old_ts)])
    assert len(old_entries) == 0


def test_switch_consecutive_builds_log(_db):
    """Switching A→B→A produces three separate SwitchLog entries."""
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import environment

    proj = _create_project()
    env_a = _create_env(proj["id"], name="env_a")
    env_b = _create_env(proj["id"], name="env_b")

    environment.switch(env_a["id"])
    environment.switch(env_b["id"])
    environment.switch(env_a["id"])

    with database_connection_manager():
        all_entries = SwitchLog.search([])
    assert len(all_entries) == 3


# ── timesheet.update_entry / delete_entry ─────────────────────────────────────

def test_timesheet_update_entry_changes_timestamp(_db):
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet

    with database_connection_manager():
        entry = SwitchLog.create({"switched_at": "2024-01-01T09:00:00", "flagged": False})
        entry_id = entry.id

    timesheet.update_entry(entry_id, "2024-01-01T10:30:00")

    with database_connection_manager():
        updated = SwitchLog.search([("id", "=", entry_id)], limit=1)
    assert updated.switched_at == "2024-01-01T10:30:00"


def test_timesheet_update_entry_unknown_raises(_db):
    from cc.services import timesheet

    with pytest.raises(NotFoundError):
        timesheet.update_entry(99999, "2024-01-01T10:00:00")


def test_timesheet_delete_entry_removes_row(_db):
    from cc.base.arm.switch_log import SwitchLog
    from cc.services import timesheet

    with database_connection_manager():
        entry = SwitchLog.create({"switched_at": "2024-01-01T09:00:00", "flagged": False})
        entry_id = entry.id

    timesheet.delete_entry(entry_id)

    with database_connection_manager():
        gone = SwitchLog.search([("id", "=", entry_id)], limit=1)
    assert not gone


def test_timesheet_delete_entry_unknown_raises(_db):
    from cc.services import timesheet

    with pytest.raises(NotFoundError):
        timesheet.delete_entry(99999)


# ── environment.update / toggle_pin (both keyed by id) ────────────────────────

def test_env_update_unknown_raises(_db):
    from cc.services import environment

    with pytest.raises(NotFoundError):
        environment.update(999999, notes="x")


def test_env_toggle_pin_flips_value(_db):
    from cc.base.arm.environment import Environment
    from cc.services import environment

    proj = _create_project()
    env = _create_env(proj["id"], name="env_pin")

    # Initially unpinned — toggle should return True
    result = environment.toggle_pin(env["id"])
    assert result is True

    with database_connection_manager():
        row = Environment.find_by(name="env_pin", limit=1)
    assert row.pinned

    # Toggle back — should return False
    result = environment.toggle_pin(env["id"])
    assert result is False

    with database_connection_manager():
        row = Environment.find_by(name="env_pin", limit=1)
    assert not row.pinned


def test_env_toggle_pin_unknown_raises(_db):
    from cc.services import environment

    with pytest.raises(NotFoundError):
        environment.toggle_pin(999999)



# ---------------------------------------------------------------------------
# pg service
# ---------------------------------------------------------------------------

def test_pg_get_last_login_returns_none_on_connection_error(monkeypatch):
    import psycopg2
    from cc.services import pg

    def fake_connect(*args, **kwargs):
        raise psycopg2.OperationalError("connection refused")

    monkeypatch.setattr(pg, "_connect", fake_connect)
    result = pg.get_last_login("some_db")
    assert result is None


def test_pg_drop_db_uses_autocommit(monkeypatch):
    from cc.services import pg

    autocommit_values = []

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql, params=None): pass

    class FakeConn:
        autocommit = False
        def cursor(self): return FakeCursor()
        def close(self): pass
        @property
        def autocommit(self): return self._autocommit
        @autocommit.setter
        def autocommit(self, v):
            autocommit_values.append(v)
            self._autocommit = v
        def __init__(self): self._autocommit = False

    monkeypatch.setattr(pg, "_connect", lambda *a, **kw: FakeConn())
    pg.drop_db("test_db")
    assert autocommit_values and autocommit_values[0] is True


def test_pg_get_last_logins_sets_is_odoo_false_on_error(monkeypatch):
    """is_odoo=False when the DB is unreachable or res_users_log is missing."""
    import psycopg2
    from cc.services import pg

    call_count = [0]

    class FakeCursor:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def execute(self, sql):
            call_count[0] += 1
            if call_count[0] == 1:
                raise psycopg2.ProgrammingError("relation does not exist")
        def fetchone(self): return ("2024-01-01",)

    class FakeConn:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def cursor(self): return FakeCursor()

    monkeypatch.setattr(pg, "_connect", lambda *a, **kw: FakeConn())
    result = pg.get_last_logins(["bad_db", "good_db"])

    assert result["bad_db"]["is_odoo"] is False
    assert result["bad_db"]["last_login"] is None
    assert result["good_db"]["is_odoo"] is True


def test_unique_together_allows_same_name_different_projects(_db):
    """Same env name is valid across different projects."""
    proj_a = _create_project("project_a")
    proj_b = _create_project("project_b")
    env_a = _create_env(proj_a["id"], name="staging")
    env_b = _create_env(proj_b["id"], name="staging")
    assert env_a["name"] == "staging"
    assert env_b["name"] == "staging"
    assert env_a["id"] != env_b["id"]


def test_unique_together_blocks_same_name_same_project(_db):
    """Same env name in the same project raises an integrity error."""
    import sqlite3
    proj = _create_project()
    _create_env(proj["id"], name="staging")
    with pytest.raises((sqlite3.IntegrityError, Exception)):
        _create_env(proj["id"], name="staging")


def test_get_status_includes_project_name(_db):
    """EnvStatusDTO carries the project name for display in cc stat."""
    from cc.services import environment
    proj = _create_project("acme")
    env = _create_env(proj["id"])
    environment.switch(env["id"])
    result = environment.get_status(verbose=True)
    assert result.environments[0].project_name == "acme"


# ── get_recent_envs ────────────────────────────────────────────────────────


def test_get_recent_envs_returns_recently_switched(_db):
    """get_recent_envs returns envs ordered by last_used_at descending."""
    from cc.services import environment
    proj = _create_project("recent_proj")
    env1 = _create_env(proj["id"], name="env_first")
    env2 = _create_env(proj["id"], name="env_second")

    # Switch to env1 then env2 — env2 should be most recent
    environment.switch(env1["id"])
    environment.switch(env2["id"])

    result = environment.get_recent_envs(limit=5)
    assert len(result) >= 2
    names = [e.name for e in result]
    assert names.index("env_second") < names.index("env_first")


def test_get_recent_envs_respects_limit(_db):
    """get_recent_envs returns at most `limit` environments."""
    from cc.services import environment
    proj = _create_project("limit_proj")
    for i in range(5):
        env = _create_env(proj["id"], name=f"env_{i}")
        environment.switch(env["id"])

    result = environment.get_recent_envs(limit=3)
    assert len(result) == 3


def test_get_recent_envs_empty_when_no_switches(_db):
    """get_recent_envs returns empty when no env has been switched to."""
    from cc.services import environment
    result = environment.get_recent_envs(limit=5)
    assert result == []


# ── get_env_modules ─────────────────────────────────────────────────────────


def test_get_env_modules_returns_sorted_names(_db):
    """get_env_modules returns the module names linked to the env, sorted."""
    from cc.services import environment
    proj = _create_project("mod_proj")
    env = _create_env(proj["id"])  # created with modules ["sale", "purchase"]
    result = environment.get_env_modules(env["id"])
    assert result == ["purchase", "sale"]


def test_get_env_modules_returns_empty_for_unknown(_db):
    """get_env_modules returns empty list for a non-existent env id."""
    from cc.services import environment
    result = environment.get_env_modules(999999)
    assert result == []
