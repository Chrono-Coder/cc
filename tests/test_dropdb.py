"""cc dropdb: single-name drop + the no-arg multiselect mass-drop. The daemon
write (database.drop) and the prompter are stubbed — no real PG, no real DB.
"""
import types


def _dropdb(monkeypatch, name=None, yes=False, checkbox=None, confirm=True,
            available=("alpha", "beta", "gamma")):
    from cc.commands.database.dropdb_command import DropdbCommand

    cmd = DropdbCommand.__new__(DropdbCommand)
    cmd.args = types.SimpleNamespace(name=name, yes=yes)

    class P:
        def __init__(self):
            self.confirms = []

        def prompt_confirm(self, msg, **kw):
            self.confirms.append(msg)
            return confirm

        def prompt_checkbox(self, options, label, **kw):
            return list(checkbox) if checkbox is not None else []

    cmd.prompter = P()
    cmd.Helpers = types.SimpleNamespace(get_all_db_names=lambda *a, **k: set(available))

    dropped = []
    monkeypatch.setattr("cc.commands.database.dropdb_command.call",
                        lambda method, **kw: dropped.append(kw["name"]))
    return cmd, dropped


def test_single_name_drops(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name="mydb", yes=True)
    assert cmd.execute() is True
    assert dropped == ["mydb"]


def test_single_name_confirm_false_aborts(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name="mydb", yes=False, confirm=False)
    assert cmd.execute() is False
    assert dropped == []
    assert len(cmd.prompter.confirms) == 1


def test_multiselect_drops_selected(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name=None, yes=True, checkbox=["alpha", "gamma"])
    assert cmd.execute() is True
    assert sorted(dropped) == ["alpha", "gamma"]


def test_multiselect_empty_selection_aborts(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name=None, yes=True, checkbox=[])
    assert cmd.execute() is False
    assert dropped == []


def test_multiselect_no_databases(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name=None, yes=True, available=())
    assert cmd.execute() is False
    assert dropped == []


def test_partial_failure_reports_false_but_drops_the_rest(monkeypatch):
    cmd, dropped = _dropdb(monkeypatch, name=None, yes=True, checkbox=["alpha", "beta"])

    def flaky(method, **kw):
        if kw["name"] == "beta":
            raise RuntimeError("boom")
        dropped.append(kw["name"])
    monkeypatch.setattr("cc.commands.database.dropdb_command.call", flaky)

    assert cmd.execute() is False     # one failed → overall False
    assert dropped == ["alpha"]       # the other still dropped
