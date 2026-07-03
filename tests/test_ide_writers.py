"""IDE writer plugin tests.

Critical regression: `cc switch` must never edit launch.json. This module
asserts that contract by hashing launch.json before and after repeated
`writer.apply()` calls — the only path that may touch launch.json is
`writer.setup()`.
"""
import hashlib
import json
from pathlib import Path

import pytest

from cc.ide import CcState, VSCodeWriter, CursorWriter
from cc.ide.registry import (
    _LAUNCHER_TO_WRITER,
    _builtin_writers,
    all_writers,
)


@pytest.fixture
def workspace(tmp_path):
    return tmp_path


@pytest.fixture
def state(workspace):
    return CcState(
        workspace_path=str(workspace),
        env_name="test-env",
        project_name="test-proj",
        version_name="17.0",
        branch="main",
        db="test_db",
        odoo_bin="/odoo/odoo-bin",
        port="8069",
        addons_path="/addons,/enterprise",
        modules="sale,account",
        upgrade_path="/upgrade-util/src",
        python_path="/venv/bin/python",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ── apply() — settings.json writes ───────────────────────────────────────


def test_apply_writes_cc_keys_to_settings(workspace, state):
    VSCodeWriter().apply(workspace, state)

    settings_path = workspace / ".vscode" / "settings.json"
    assert settings_path.exists()
    settings = json.loads(settings_path.read_text())

    assert settings["cc.odooBin"] == "/odoo/odoo-bin"
    assert settings["cc.port"] == "8069"
    assert settings["cc.database"] == "test_db"
    assert settings["cc.addonsPath"] == "/addons,/enterprise"
    assert settings["cc.modules"] == "sale,account"
    assert settings["cc.upgradePath"] == "/upgrade-util/src"
    assert settings["cc.initMode"] == "-u"
    assert settings["python.defaultInterpreterPath"] == "/venv/bin/python"


def test_apply_preserves_unrelated_settings(workspace, state):
    vscode_dir = workspace / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "settings.json").write_text(
        json.dumps({"editor.fontSize": 14, "files.exclude": {".git": True}})
    )

    VSCodeWriter().apply(workspace, state)

    settings = json.loads((vscode_dir / "settings.json").read_text())
    assert settings["editor.fontSize"] == 14
    assert settings["files.exclude"] == {".git": True}
    assert settings["cc.database"] == "test_db"


def test_apply_is_idempotent(workspace, state):
    writer = VSCodeWriter()
    writer.apply(workspace, state)
    first = _sha(workspace / ".vscode" / "settings.json")
    writer.apply(workspace, state)
    second = _sha(workspace / ".vscode" / "settings.json")
    assert first == second


def test_apply_skips_empty_fields(workspace):
    state = CcState(
        workspace_path=str(workspace),
        env_name="", project_name="", version_name="", branch="",
        db="",                           # empty → key should not be written
        odoo_bin="/x/odoo-bin",
        port="8069",
        addons_path="",                  # empty → skip
        modules="",                      # empty → skip
        upgrade_path="",                 # empty → skip
        python_path="",                  # empty → skip
    )
    VSCodeWriter().apply(workspace, state)

    settings = json.loads((workspace / ".vscode" / "settings.json").read_text())
    assert "cc.database" not in settings
    assert "cc.addonsPath" not in settings
    assert "cc.modules" not in settings
    assert "cc.upgradePath" not in settings
    assert "python.defaultInterpreterPath" not in settings
    # initMode is always set via setdefault
    assert settings["cc.initMode"] == "-u"
    # Provided fields still land
    assert settings["cc.odooBin"] == "/x/odoo-bin"
    assert settings["cc.port"] == "8069"


def test_apply_preserves_user_init_mode(workspace, state):
    vscode_dir = workspace / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "settings.json").write_text(json.dumps({"cc.initMode": "-i"}))

    VSCodeWriter().apply(workspace, state)

    settings = json.loads((vscode_dir / "settings.json").read_text())
    # setdefault means existing values stick
    assert settings["cc.initMode"] == "-i"


# ── setup() — launch.json writes ─────────────────────────────────────────


def test_setup_writes_launch_template(workspace):
    VSCodeWriter().setup(workspace)
    launch = json.loads((workspace / ".vscode" / "launch.json").read_text())
    names = {c["name"] for c in launch.get("configurations", [])}
    assert "CC: Odoo" in names
    assert "CC: Odoo [test]" in names


def test_setup_preserves_user_configs(workspace):
    vscode_dir = workspace / ".vscode"
    vscode_dir.mkdir()
    user_config = {
        "version": "0.2.0",
        "configurations": [
            {"name": "My Custom Config", "type": "python", "request": "launch"}
        ],
        "inputs": [],
    }
    (vscode_dir / "launch.json").write_text(json.dumps(user_config))

    VSCodeWriter().setup(workspace)

    launch = json.loads((vscode_dir / "launch.json").read_text())
    names = {c["name"] for c in launch["configurations"]}
    assert "My Custom Config" in names
    assert "CC: Odoo" in names


def test_setup_replaces_existing_cc_entries(workspace):
    vscode_dir = workspace / ".vscode"
    vscode_dir.mkdir()
    (vscode_dir / "launch.json").write_text(
        json.dumps({
            "version": "0.2.0",
            "configurations": [
                {"name": "CC: Odoo", "type": "stale", "request": "launch"}
            ],
            "inputs": [],
        })
    )

    VSCodeWriter().setup(workspace)

    launch = json.loads((vscode_dir / "launch.json").read_text())
    cc_odoo = [c for c in launch["configurations"] if c["name"] == "CC: Odoo"]
    assert len(cc_odoo) == 1
    assert cc_odoo[0]["type"] == "debugpy"  # fresh from template


# ── REGRESSION: apply() must NEVER touch launch.json ─────────────────────


def test_apply_never_touches_launch_json(workspace, state):
    writer = VSCodeWriter()
    writer.setup(workspace)
    launch_path = workspace / ".vscode" / "launch.json"
    before = _sha(launch_path)

    # Apply many times with varying state — launch.json must not change.
    for db in ["a", "b", "c", "d", "e"]:
        modified = CcState(**{**state.__dict__, "db": db})
        writer.apply(workspace, modified)

    after = _sha(launch_path)
    assert before == after, "cc switch path (apply) edited launch.json — contract violation"


def test_apply_does_not_create_launch_json(workspace, state):
    """If setup() hasn't run, apply() must still not create launch.json."""
    VSCodeWriter().apply(workspace, state)
    assert (workspace / ".vscode" / "settings.json").exists()
    assert not (workspace / ".vscode" / "launch.json").exists()


# ── detect() ─────────────────────────────────────────────────────────────


def test_detect_vscode_via_dotvscode_dir(workspace, monkeypatch):
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    assert VSCodeWriter().detect(workspace) is False
    (workspace / ".vscode").mkdir()
    assert VSCodeWriter().detect(workspace) is True


def test_detect_vscode_via_term_program(tmp_path, monkeypatch):
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    assert VSCodeWriter().detect(tmp_path) is True


def test_detect_cursor_requires_explicit_env(tmp_path, monkeypatch):
    # Cursor sets TERM_PROGRAM=vscode for compat; that alone is NOT enough.
    monkeypatch.setenv("TERM_PROGRAM", "vscode")
    monkeypatch.delenv("CURSOR_TRACE_ID", raising=False)
    assert CursorWriter().detect(tmp_path) is False

    monkeypatch.setenv("CURSOR_TRACE_ID", "abc")
    assert CursorWriter().detect(tmp_path) is True


# ── registry ─────────────────────────────────────────────────────────────


def test_builtin_writers_include_vscode_and_cursor():
    names = {w.name for w in _builtin_writers()}
    assert "vscode" in names
    assert "cursor" in names


def test_all_writers_includes_builtins():
    names = {w.name for w in all_writers()}
    assert "vscode" in names
    assert "cursor" in names


def test_legacy_launcher_values_map_to_writer_names():
    assert _LAUNCHER_TO_WRITER["code"] == "vscode"
    assert _LAUNCHER_TO_WRITER["cursor"] == "cursor"
    assert _LAUNCHER_TO_WRITER["vscode"] == "vscode"
