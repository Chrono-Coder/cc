"""
Workspace service tests — use the `_db` fixture so no real DB is touched.

Covers: create, get_all, update, delete, assign_project, migration backfill.
"""
import pytest
from cc.utils.errors import NotFoundError

from cc.base.db import database_connection_manager


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_version(name="17.0", path="/opt/v17"):
    from cc.services import version
    return version.create(name, path, branch=name)


def _create_workspace(name="ws_test", path="", is_rnd=False, version_id=0):
    from cc.services import workspace
    return workspace.create(name=name, path=path, is_rnd=is_rnd, version_id=version_id)


def _create_project(name="test_project"):
    from cc.services import project
    return project.create(name)


def _create_env(project_id, version_name="17.0", name="test_env"):
    from cc.services import environment
    return environment.create(
        name=name,
        project_id=project_id,
        version_name=version_name,
        version_path="/opt/v17",
        project_path="/tmp/myproject",
        github_url="",
        branch_name="main",
        database_name="test_db",
        module_names=[],
    )


# ── workspace.create ──────────────────────────────────────────────────────────

def test_workspace_create_returns_id_and_name(_db):
    from cc.services import workspace
    result = workspace.create(name="acme")
    assert result["id"] > 0
    assert result["name"] == "acme"


def test_workspace_create_with_version(_db):
    from cc.base.arm.workspace import Workspace
    v = _create_version()
    result = _create_workspace(name="v17_ws", version_id=v["id"])
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
        version_id = ws.version_id.id
    assert version_id == v["id"]


def test_workspace_create_rnd_flag(_db):
    from cc.base.arm.workspace import Workspace
    result = _create_workspace(name="rnd_ws", is_rnd=True)
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
    assert ws.is_rnd is True


def test_workspace_create_with_path(_db):
    from cc.base.arm.workspace import Workspace
    result = _create_workspace(name="path_ws", path="/home/odoo/rnd")
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
    assert ws.path == "/home/odoo/rnd"


# ── workspace.get_all ─────────────────────────────────────────────────────────

def test_workspace_get_all_empty(_db):
    from cc.services import workspace
    assert workspace.get_all() == []


def test_workspace_get_all_returns_all(_db):
    from cc.services import workspace
    _create_workspace("alpha")
    _create_workspace("beta")
    results = workspace.get_all()
    names = [w["name"] for w in results]
    assert "alpha" in names
    assert "beta" in names


def test_workspace_get_all_sorted_by_name(_db):
    from cc.services import workspace
    _create_workspace("zebra")
    _create_workspace("apple")
    results = workspace.get_all()
    names = [w["name"] for w in results]
    assert names == sorted(names)


def test_workspace_get_all_includes_version_name(_db):
    from cc.services import workspace
    v = _create_version("18.0", "/opt/v18")
    _create_workspace("ws_with_version", version_id=v["id"])
    results = workspace.get_all()
    ws = next(w for w in results if w["name"] == "ws_with_version")
    assert ws["version_name"] == "18.0"
    assert ws["version_id"] == v["id"]


def test_workspace_get_all_version_name_none_when_unlinked(_db):
    from cc.services import workspace
    _create_workspace("unlinked_ws")
    results = workspace.get_all()
    ws = next(w for w in results if w["name"] == "unlinked_ws")
    assert ws["version_name"] is None
    assert ws["version_id"] is None


# ── workspace.update ──────────────────────────────────────────────────────────

def test_workspace_update_name(_db):
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    result = _create_workspace("old_name")
    workspace.update(result["id"], name="new_name")
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
    assert ws.name == "new_name"


def test_workspace_update_path(_db):
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    result = _create_workspace("ws_path")
    workspace.update(result["id"], path="/new/path")
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
    assert ws.path == "/new/path"


def test_workspace_update_is_rnd(_db):
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    result = _create_workspace("ws_rnd")
    workspace.update(result["id"], is_rnd=True)
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
    assert ws.is_rnd is True


def test_workspace_update_version(_db):
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    v = _create_version("16.0", "/opt/v16")
    result = _create_workspace("ws_ver")
    workspace.update(result["id"], version_id=v["id"])
    with database_connection_manager():
        ws = Workspace.search([("id", "=", result["id"])], limit=1)
        version_id = ws.version_id.id
    assert version_id == v["id"]


def test_workspace_update_unknown_raises(_db):
    from cc.services import workspace
    with pytest.raises(NotFoundError):
        workspace.update(99999, name="ghost")


# ── workspace.delete ──────────────────────────────────────────────────────────

def test_workspace_delete_removes_record(_db):
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    result = _create_workspace("to_delete")
    workspace.delete(result["id"])
    with database_connection_manager():
        assert not Workspace.search([("id", "=", result["id"])], limit=1)


def test_workspace_delete_unlinks_projects(_db):
    """Deleting a workspace sets project.workspace_id to NULL, not delete the project."""
    from cc.base.arm.project import Project
    from cc.services import workspace
    ws = _create_workspace("ws_with_proj")
    proj = _create_project("linked_project")
    workspace.assign_project(ws["id"], proj["id"])

    workspace.delete(ws["id"])

    with database_connection_manager():
        p = Project.search([("id", "=", proj["id"])], limit=1)
        ws_id = p.workspace_id.id if p.workspace_id else None
    assert p is not None  # project still exists
    assert ws_id is None  # but unlinked


def test_workspace_delete_unknown_raises(_db):
    from cc.services import workspace
    with pytest.raises(NotFoundError):
        workspace.delete(99999)


# ── workspace.assign_project ──────────────────────────────────────────────────

def test_assign_project_links_project(_db):
    from cc.base.arm.project import Project
    from cc.services import workspace
    ws = _create_workspace("ws_assign")
    proj = _create_project("proj_to_assign")
    workspace.assign_project(ws["id"], proj["id"])
    with database_connection_manager():
        p = Project.search([("id", "=", proj["id"])], limit=1)
        ws_id = p.workspace_id.id
    assert ws_id == ws["id"]


def test_assign_project_unknown_workspace_raises(_db):
    from cc.services import workspace
    proj = _create_project("orphan_proj")
    with pytest.raises(NotFoundError):
        workspace.assign_project(99999, proj["id"])


def test_assign_project_unknown_project_raises(_db):
    from cc.services import workspace
    ws = _create_workspace("ws_no_proj")
    with pytest.raises(NotFoundError):
        workspace.assign_project(ws["id"], 99999)


def test_assign_project_reflected_in_workspace_project_ids(_db):
    """After assignment, workspace.project_ids must include the linked project."""
    from cc.base.arm.workspace import Workspace
    from cc.services import workspace
    ws = _create_workspace("ws_o2m")
    proj_a = _create_project("proj_a")
    proj_b = _create_project("proj_b")
    workspace.assign_project(ws["id"], proj_a["id"])
    workspace.assign_project(ws["id"], proj_b["id"])
    with database_connection_manager():
        ws_orm = Workspace.search([("id", "=", ws["id"])], limit=1)
        ids = {p.id for p in ws_orm.project_ids}
    assert proj_a["id"] in ids
    assert proj_b["id"] in ids


# ── migration backfill logic (v6/v7) ─────────────────────────────────────────

def test_migration_backfill_creates_workspace_per_version(_db):
    """
    Simulate v6 migration: a workspace must be created for each version that
    has environments. Versions with no envs are skipped.
    """
    from cc.base.db import get_db_connection

    proj = _create_project()
    v17 = _create_version("17.0", "/opt/v17")
    _create_env(proj["id"], version_name="17.0")

    # Run v6 SQL directly (simulate migration on existing data)
    with database_connection_manager():
        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO workspace (name, path, is_rnd, version_id)"
            " SELECT v.name, v.path, 0, v.id"
            " FROM version v"
            " WHERE EXISTS (SELECT 1 FROM environment e WHERE e.version_id = v.id)"
        )
        rows = conn.execute("SELECT name FROM workspace WHERE version_id = ?", (v17["id"],)).fetchall()

    assert len(rows) == 1
    assert rows[0][0] == "17.0"


def test_migration_backfill_skips_version_without_envs(_db):
    """Versions with no environments must not get a workspace in v6 migration."""
    from cc.base.db import get_db_connection

    _create_version("16.0", "/opt/v16")  # no environments linked

    with database_connection_manager():
        conn = get_db_connection()
        conn.execute(
            "INSERT OR IGNORE INTO workspace (name, path, is_rnd, version_id)"
            " SELECT v.name, v.path, 0, v.id"
            " FROM version v"
            " WHERE EXISTS (SELECT 1 FROM environment e WHERE e.version_id = v.id)"
        )
        rows = conn.execute("SELECT name FROM workspace WHERE name = '16.0'").fetchall()

    assert len(rows) == 0


def test_migration_backfill_assigns_project_to_workspace(_db):
    """v7 migration must set project.workspace_id from its first environment's version."""
    from cc.base.db import get_db_connection

    proj = _create_project("backfill_proj")
    _create_version("17.0", "/opt/v17")
    _create_env(proj["id"], version_name="17.0")

    with database_connection_manager():
        conn = get_db_connection()
        # Run v6 first
        conn.execute(
            "INSERT OR IGNORE INTO workspace (name, path, is_rnd, version_id)"
            " SELECT v.name, v.path, 0, v.id"
            " FROM version v"
            " WHERE EXISTS (SELECT 1 FROM environment e WHERE e.version_id = v.id)"
        )
        # Run v7
        conn.execute(
            "UPDATE project SET workspace_id = ("
            "  SELECT w.id FROM workspace w"
            "  INNER JOIN environment e ON e.version_id = w.version_id AND e.project_id = project.id"
            "  LIMIT 1"
            ") WHERE workspace_id IS NULL"
        )
        row = conn.execute(
            "SELECT workspace_id FROM project WHERE id = ?", (proj["id"],)
        ).fetchone()

    assert row is not None
    assert row[0] is not None  # workspace_id was set


# ── ensure_workspaces (synced multi-device safety) ────────────────────────────

def test_ensure_workspaces_skips_nonlocal_and_name_collisions(_db, tmp_path, monkeypatch):
    """Regression: in a DB synced across devices, ensure_workspaces() must only
    bootstrap versions whose path exists on THIS machine, and must never collide
    on the unique workspace.name. Previously a synced version named like a local
    workspace (e.g. another device's '17') crashed with
    'UNIQUE constraint failed: workspace.name'.
    """
    from cc.services import workspace as ws_service
    from cc.workspace import registration

    # No daemon in tests: route the two RPCs ensure_workspaces uses to the
    # services directly, and stub the IDE-template side effect.
    def fake_call(method, **kwargs):
        if method == "workspace.get_all":
            return ws_service.get_all()
        if method == "workspace.create":
            return ws_service.create(**kwargs)
        raise AssertionError(f"unexpected daemon call: {method}")
    monkeypatch.setattr(registration, "call", fake_call)
    monkeypatch.setattr(registration, "_ensure_ide_templates", lambda paths: None)

    # Local version, path exists, no workspace yet → should be bootstrapped.
    local_dir = tmp_path / "odoo-v17"
    local_dir.mkdir()
    _create_version("v17", str(local_dir))

    # Synced/remote version: path absent here → skipped by the local-path filter
    # (and its name collides with an existing workspace, which used to crash).
    _create_version("17", "/nonexistent/Users/peter/odoo/17")
    _create_workspace("17")

    # Local version whose name already belongs to a workspace → skipped by the
    # name guard even though its path exists.
    local16 = tmp_path / "odoo-v16"
    local16.mkdir()
    _create_version("16", str(local16))
    _create_workspace("16")

    # ensure_workspaces() does a bare ORM read; the CLI runs it inside an ambient
    # DB context, so the test supplies one too (the manager is re-entrant, so the
    # nested service calls reuse this connection).
    with database_connection_manager():
        created = registration.ensure_workspaces()

    assert created == ["v17"]  # only the genuinely-local, unclaimed version
    names = [w["name"] for w in ws_service.get_all()]
    assert names.count("17") == 1  # no duplicate, no crash
    assert "v17" in names
