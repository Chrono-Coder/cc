from pathlib import Path
from types import SimpleNamespace

import pytest

from cc.runtime.odoo import OdooRuntime
from cc.utils.constants import Constants
from cc.utils.errors import CCError


class _Helpers:
    @staticmethod
    def pyenv_get_python_path(name):
        return f"/pyenv/{name}/bin/python"


def _command(tmp_path: Path, *, database="acme", venv=None):
    version_path = tmp_path / "19.0"
    (version_path / "odoo").mkdir(parents=True)
    (version_path / "odoo" / "odoo-bin").touch()
    env = SimpleNamespace(
        project_path=str(tmp_path / "project"),
        database_id=SimpleNamespace(name=database) if database else None,
        module_ids=[],
    )
    version = SimpleNamespace(
        id=19, name="19.0", path=str(version_path), port="8079", pyenv_virtualenv=venv,
    )
    return SimpleNamespace(
        active_environment=env, active_version=version, Constants=Constants, Helpers=_Helpers,
    )


def test_runtime_builds_server_and_shell_commands(tmp_path, monkeypatch):
    monkeypatch.setattr("cc.services.environment.get_addons_path", lambda version_id: "/a,/b")
    monkeypatch.setattr("cc.runtime.odoo._path_python", lambda: "/usr/bin/python3")
    runtime = OdooRuntime.from_command(_command(tmp_path))

    assert runtime.python == "/usr/bin/python3"
    assert runtime.command("server")[-5:] == ["-p", "8079", "-d", "acme", "--dev=all"]
    assert runtime.command("shell")[-5:] == ["-p", "8079", "-d", "acme", "shell"]
    assert "--addons-path=/a,/b" in runtime.command("server")


def test_runtime_database_override_supports_fresh_creation(tmp_path, monkeypatch):
    monkeypatch.setattr("cc.services.environment.get_addons_path", lambda version_id: None)
    runtime = OdooRuntime.from_command(_command(tmp_path, database=None), database="fresh-db")
    assert runtime.database == "fresh-db"


def test_runtime_adds_persisted_install_and_upgrade_actions(tmp_path, monkeypatch):
    monkeypatch.setattr("cc.services.environment.get_addons_path", lambda version_id: None)
    command = _command(tmp_path)
    command.active_environment.module_ids = [
        SimpleNamespace(name="sale_custom", state="install"),
        SimpleNamespace(name="stock_custom", state="upgrade"),
        SimpleNamespace(name="draft_custom", state="draft"),
    ]
    runtime = OdooRuntime.from_command(command)

    argv = runtime.command("server")
    assert argv[-4:] == ["-i", "sale_custom", "-u", "stock_custom"]
    assert "draft_custom" not in argv


def test_runtime_requires_an_active_database(tmp_path):
    with pytest.raises(CCError, match="No database selected"):
        OdooRuntime.from_command(_command(tmp_path, database=None))


def test_runtime_rejects_a_broken_virtualenv(tmp_path):
    with pytest.raises(CCError, match="Python for virtualenv"):
        OdooRuntime.from_command(_command(tmp_path, venv="odoo19"))


def test_path_python_excludes_ccs_own_virtualenv(monkeypatch):
    from cc.runtime.odoo import _path_python

    monkeypatch.setenv("VIRTUAL_ENV", "/cc-venv")
    monkeypatch.setenv("PATH", "/cc-venv/bin:/usr/bin:/bin")
    monkeypatch.setattr("cc.runtime.odoo.sys.prefix", "/cc-venv")
    monkeypatch.setattr(
        "cc.runtime.odoo.shutil.which",
        lambda executable, path: "/usr/bin/python3" if "/cc-venv/bin" not in path else None,
    )
    completed = SimpleNamespace(stdout="/usr/bin/python3\n")
    monkeypatch.setattr("cc.runtime.odoo.subprocess.run", lambda *args, **kwargs: completed)

    assert _path_python() == "/usr/bin/python3"
