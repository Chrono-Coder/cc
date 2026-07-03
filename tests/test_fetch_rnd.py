"""
R&D-aware fetch (3.8): `cc fetch` must never restore+pull on an R&D workspace
(that would discard uncommitted work) — it fetch-only's there. Source checkouts,
never hand-edited, still get the restore+pull that keeps them pristine.

Here we pin the decision helper `_version_is_rnd`; the fetch-function selection
in _execute_multi_dir keys off it.
"""
from cc.base.db import database_connection_manager


def _fetch_cmd():
    from cc.commands.git.fetch_command import FetchCommand
    return FetchCommand(skip_add_parser=True)


def test_version_is_rnd_true_for_rnd_workspace(_db):
    from cc.services import version, workspace
    from cc.base.arm.version import Version

    v = version.create("rnd", "/opt/rnd", branch="19.0-feat")
    workspace.create(name="ws-rnd", path="/opt/rnd", is_rnd=True, version_id=v["id"])

    cmd = _fetch_cmd()
    with database_connection_manager():
        rec = Version.find_by(name="rnd", limit=1)
        assert cmd._version_is_rnd(rec) is True


def test_version_is_rnd_false_for_source_workspace(_db):
    from cc.services import version, workspace
    from cc.base.arm.version import Version

    v = version.create("src", "/opt/src", branch="17.0")
    workspace.create(name="ws-src", path="/opt/src", is_rnd=False, version_id=v["id"])

    cmd = _fetch_cmd()
    with database_connection_manager():
        rec = Version.find_by(name="src", limit=1)
        assert cmd._version_is_rnd(rec) is False


def test_version_is_rnd_false_when_no_workspace(_db):
    """A version with no workspace at all isn't R&D — fetch treats it as source."""
    from cc.services import version
    from cc.base.arm.version import Version

    version.create("orphan", "/opt/orphan", branch="18.0")

    cmd = _fetch_cmd()
    with database_connection_manager():
        rec = Version.find_by(name="orphan", limit=1)
        assert cmd._version_is_rnd(rec) is False
