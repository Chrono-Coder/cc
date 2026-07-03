"""
`cc daemon --quiet` (3.8): the shell auto-start runs `cc daemon status --quiet`
and starts the daemon only if it exits non-zero. So quiet status must return
False (→ exit 1) when the daemon is down and True when it's up, silently. And
execute() must propagate the action's return value so that exit code lands.

Also pins client._socket_is_live(): stale-socket detection connects rather than
trusting the socket file's existence.
"""
from argparse import Namespace

from cc.commands.system.daemon_command import DaemonStatusCommand


def _status_cmd(quiet=True):
    c = DaemonStatusCommand(skip_add_parser=True)
    c.args = Namespace(quiet=quiet)
    return c


def test_quiet_status_returns_false_when_down(monkeypatch):
    c = _status_cmd(quiet=True)
    monkeypatch.setattr(c, "_read_pid", lambda: None)
    assert c._status() is False


def test_quiet_status_returns_true_when_up(monkeypatch):
    c = _status_cmd(quiet=True)
    monkeypatch.setattr(c, "_read_pid", lambda: 4242)
    monkeypatch.setattr(c, "_is_running", lambda pid: True)
    assert c._status() is True


def test_execute_propagates_status_result(monkeypatch):
    c = _status_cmd(quiet=True)
    monkeypatch.setattr(c, "_read_pid", lambda: None)
    # execute() routes to _status(); its False must bubble up for exit-code 1.
    assert c.execute() is False


def test_socket_not_live_when_file_absent(tmp_path, monkeypatch):
    from cc.daemon import client
    from cc.utils.constants import Constants

    monkeypatch.setattr(Constants, "SOCKET_PATH", str(tmp_path / "absent.sock"))
    assert client._socket_is_live() is False
