"""
ORM layer tests — focused on one2many command processing on both create and update paths.

Uses the Environment → Module relationship (module_ids / environment_id) as the
canonical o2m pair since it's the most exercised in production.
"""
import pytest

from cc.base.db import database_connection_manager


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def project(_db):
    from cc.base.arm.project import Project
    with database_connection_manager():
        return Project.create({"name": "test-project"})


@pytest.fixture
def version(_db):
    from cc.base.arm.version import Version
    with database_connection_manager():
        return Version.create({"name": "19.0", "path": "/odoo/19"})


def _env(name, project, version, path="/projects/test"):
    """Create a minimal valid Environment inside the current connection context."""
    from cc.base.arm.environment import Environment
    return Environment.create({
        "name": name,
        "project_id": project.id,
        "project_path": path,
        "version_id": version.id,
    })


@pytest.fixture
def env(project, version):
    with database_connection_manager():
        return _env("test-env", project, version)


# ── cmd_type 0 — CREATE children on create ───────────────────────────────────

def test_o2m_create_cmd0_creates_children(_db, project, version):
    from cc.base.arm.environment import Environment
    from cc.base.arm.module import Module

    with database_connection_manager():
        env = Environment.create({
            "name": "env-with-modules",
            "project_id": project.id,
            "project_path": "/projects/test",
            "version_id": version.id,
            "module_ids": [
                (0, 0, {"name": "sale"}),
                (0, 0, {"name": "purchase"}),
            ],
        })

    with database_connection_manager():
        modules = Module.search([("environment_id", "=", env.id)])
        names = {m.name for m in modules}

    assert names == {"sale", "purchase"}


def test_o2m_create_cmd0_sets_inverse_fk(_db, project, version):
    from cc.base.arm.environment import Environment
    from cc.base.arm.module import Module

    with database_connection_manager():
        env = Environment.create({
            "name": "env-fk-check",
            "project_id": project.id,
            "project_path": "/projects/test",
            "version_id": version.id,
            "module_ids": [(0, 0, {"name": "stock"})],
        })

    with database_connection_manager():
        mod = Module.search([("environment_id", "=", env.id)], limit=1)
        assert mod is not None
        assert mod.environment_id.id == env.id


# ── cmd_type 4 — LINK existing records on create ─────────────────────────────

def test_o2m_create_cmd4_links_existing_record(_db, project, version):
    from cc.base.arm.module import Module

    with database_connection_manager():
        orphan = _env("orphan-env", project, version)
        mod = Module.create({"name": "crm", "environment_id": orphan.id})

    with database_connection_manager():
        target = _env("env-link", project, version)

    with database_connection_manager():
        from cc.base.arm.environment import Environment
        e = Environment.find(target.id)
        e.update({"module_ids": [(4, mod.id, 0)]})

    with database_connection_manager():
        linked = Module.search([("environment_id", "=", target.id)])

    assert any(m.id == mod.id for m in linked)


# ── cmd_type 6 — REPLACE (link listed ids) on create ─────────────────────────

def test_o2m_create_cmd6_links_all_listed_ids(_db, project, version):
    from cc.base.arm.module import Module

    with database_connection_manager():
        base = _env("base-env", project, version)
        mod1 = Module.create({"name": "account", "environment_id": base.id})
        mod2 = Module.create({"name": "hr", "environment_id": base.id})

    with database_connection_manager():
        target = _env("env-replace", project, version)

    with database_connection_manager():
        from cc.base.arm.environment import Environment
        e = Environment.find(target.id)
        e.update({"module_ids": [(6, 0, [mod1.id, mod2.id])]})

    with database_connection_manager():
        linked = Module.search([("environment_id", "=", target.id)])
        linked_ids = {m.id for m in linked}

    assert mod1.id in linked_ids
    assert mod2.id in linked_ids


# ── cmd_type 0 on update — sanity check existing path still works ─────────────

def test_o2m_update_cmd0_adds_child(_db, env):
    from cc.base.arm.environment import Environment
    from cc.base.arm.module import Module

    with database_connection_manager():
        e = Environment.find(env.id)
        e.update({"module_ids": [(0, 0, {"name": "website"})]})

    with database_connection_manager():
        modules = Module.search([("environment_id", "=", env.id)])

    assert any(m.name == "website" for m in modules)


def test_o2m_update_cmd5_clears_children(_db, env):
    from cc.base.arm.environment import Environment
    from cc.base.arm.module import Module

    with database_connection_manager():
        e = Environment.find(env.id)
        e.update({"module_ids": [
            (0, 0, {"name": "mod_a"}),
            (0, 0, {"name": "mod_b"}),
        ]})

    with database_connection_manager():
        e = Environment.find(env.id)
        e.update({"module_ids": [(5, 0, 0)]})

    with database_connection_manager():
        remaining = Module.search([("environment_id", "=", env.id)])

    assert len(remaining) == 0


def test_o2m_update_cmd6_replaces_children(_db, env, project, version):
    from cc.base.arm.environment import Environment
    from cc.base.arm.module import Module

    with database_connection_manager():
        e = Environment.find(env.id)
        e.update({"module_ids": [(0, 0, {"name": "old_mod"})]})

    with database_connection_manager():
        staging = _env("staging", project, version)
        keeper = Module.create({"name": "keeper", "environment_id": staging.id})

    with database_connection_manager():
        e = Environment.find(env.id)
        e.update({"module_ids": [(6, 0, [keeper.id])]})

    with database_connection_manager():
        remaining = Module.search([("environment_id", "=", env.id)])
        names = {m.name for m in remaining}

    assert "keeper" in names
    assert "old_mod" not in names


def test_update_clears_m2one_relation(_db):
    """update({rel: None}) must persist as NULL. Previously save() skipped None,
    so a many2one could never be cleared (silently broke workspace unassign)."""
    from cc.base.arm.project import Project
    from cc.base.arm.workspace import Workspace

    with database_connection_manager():
        ws = Workspace.create({"name": "ws-clear", "path": "/tmp/ws"})
        proj = Project.create({"name": "p-clear", "workspace_id": ws.id})
        assert proj.workspace_id and proj.workspace_id.id == ws.id
        proj.update({"workspace_id": None})

    with database_connection_manager():
        reloaded = Project.find_by(name="p-clear", limit=1)
        assert not reloaded.workspace_id  # actually cleared now
