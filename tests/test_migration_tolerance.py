"""The migration runner skips an index/backfill migration whose table is absent
(an optional plugin isn't installed) without marking it applied — so it runs once
the plugin's models register the table. Genuine sqlite errors still raise."""
import pytest

from cc.base import migrations as m
from cc.base.db import database_connection_manager, get_db_connection


def test_missing_optional_table_is_skipped_not_fatal(_db, monkeypatch):
    good = m.Migration(99001, "index on a core table", "CREATE INDEX IF NOT EXISTS t_name ON setting(name)")
    plugin = m.Migration(99002, "index on an absent plugin table", "CREATE INDEX IF NOT EXISTS p_x ON plugin_tbl(x)")
    monkeypatch.setattr(m, "MIGRATIONS", [good, plugin])

    with database_connection_manager():
        m.run_migrations()  # must NOT raise though plugin_tbl doesn't exist
        applied = m._get_applied_versions(get_db_connection())

    assert 99001 in applied          # the valid one applied
    assert 99002 not in applied      # the absent-table one skipped → retries later


def test_real_sql_error_still_raises(_db, monkeypatch):
    bad = m.Migration(99003, "syntactically broken", "CREATE INDEX bad SYNTAX")
    monkeypatch.setattr(m, "MIGRATIONS", [bad])
    with database_connection_manager():
        with pytest.raises(RuntimeError):
            m.run_migrations()
