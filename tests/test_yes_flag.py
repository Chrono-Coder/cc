"""
Tests for -y/--yes flag on destructive commands.

Only tests the confirmation gate — actual deletion is covered in test_services.py.
Patches cc.daemon.client.call to avoid daemon dependency.
"""
import types


def _args(**kwargs):
    defaults = {"yes": False, "name": None}
    defaults.update(kwargs)
    return types.SimpleNamespace(**defaults)


def _make_prompter(confirm_return):
    calls = []

    class P:
        def prompt_confirm(self, msg, **kw):
            calls.append(msg)
            return confirm_return

        def prompt_autocomplete(self, choices, msg, **kw):
            return choices[0] if choices else None
    p = P()
    p._calls = calls
    return p


# ── project remove ────────────────────────────────────────────────────────────

def _project_cmd(yes, confirm_return, monkeypatch):
    from cc.commands.project.project_command import ProjectCommand
    cmd = ProjectCommand.__new__(ProjectCommand)
    cmd.args = _args(yes=yes)
    cmd.prompter = _make_prompter(confirm_return)
    deleted = []
    monkeypatch.setattr("cc.commands.project.project_command.call",
                        lambda method, **kw: deleted.append(kw))
    return cmd, deleted


def test_project_remove_yes_skips_confirm_and_deletes(monkeypatch):
    cmd, deleted = _project_cmd(yes=True, confirm_return=False, monkeypatch=monkeypatch)
    proj = types.SimpleNamespace(id=1, name="acme")
    result = cmd._execute_remove(proj)
    assert not cmd.prompter._calls
    assert any(d.get("project_id") == 1 for d in deleted)
    assert result is True


def test_project_remove_no_yes_confirm_true_deletes(monkeypatch):
    cmd, deleted = _project_cmd(yes=False, confirm_return=True, monkeypatch=monkeypatch)
    proj = types.SimpleNamespace(id=2, name="beta")
    result = cmd._execute_remove(proj)
    assert len(cmd.prompter._calls) == 1
    assert any(d.get("project_id") == 2 for d in deleted)
    assert result is True


def test_project_remove_no_yes_confirm_false_aborts(monkeypatch):
    cmd, deleted = _project_cmd(yes=False, confirm_return=False, monkeypatch=monkeypatch)
    proj = types.SimpleNamespace(id=3, name="gamma")
    result = cmd._execute_remove(proj)
    assert len(cmd.prompter._calls) == 1
    assert not deleted
    assert result is False


# ── env remove ────────────────────────────────────────────────────────────────

def _env_cmd(yes, confirm_return, monkeypatch):
    from cc.commands.project.environment_command import EnvironmentCommand
    cmd = EnvironmentCommand.__new__(EnvironmentCommand)
    cmd.args = _args(yes=yes, target=None)
    cmd.prompter = _make_prompter(confirm_return)
    deleted = []
    monkeypatch.setattr("cc.commands.project.environment_command.call",
                        lambda method, **kw: deleted.append(kw))
    env = types.SimpleNamespace(id=10, name="staging")
    monkeypatch.setattr(cmd, "_resolve_environment",
                        lambda target, action="remove": env)
    # The PG-drop cascade reads the linked DB from the ORM; stub it (no DB in unit tests).
    monkeypatch.setattr(cmd, "_linked_db_for_drop", lambda e: (None, False))
    return cmd, deleted, env


def test_env_remove_yes_skips_confirm_and_deletes(monkeypatch):
    cmd, deleted, env = _env_cmd(yes=True, confirm_return=False, monkeypatch=monkeypatch)
    result = cmd._execute_env_remove(None)
    assert not cmd.prompter._calls
    assert any(d.get("env_id") == 10 for d in deleted)
    assert result is True


def test_env_remove_no_yes_confirm_true_deletes(monkeypatch):
    cmd, deleted, env = _env_cmd(yes=False, confirm_return=True, monkeypatch=monkeypatch)
    result = cmd._execute_env_remove(None)
    assert len(cmd.prompter._calls) == 1
    assert any(d.get("env_id") == 10 for d in deleted)
    assert result is True


def test_env_remove_no_yes_confirm_false_aborts(monkeypatch):
    cmd, deleted, env = _env_cmd(yes=False, confirm_return=False, monkeypatch=monkeypatch)
    result = cmd._execute_env_remove(None)
    assert len(cmd.prompter._calls) == 1
    assert not deleted
    assert result is False


# `cc db --remove` is gone — drop is now `cc db drop` (DropdbCommand), covered by
# test_dropdb.py (single + multiselect + confirm gate + partial-failure).
