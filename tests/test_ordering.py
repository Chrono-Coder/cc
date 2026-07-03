"""
Deterministic list ordering (3.8): the founder reported pickers/lists shuffling
between runs. Root cause was ORM reads with no ORDER BY (SQLite rowid order).
Fix: BaseEntity._order defaults reads to a stable key; display models override
to "name ASC". Explicit orderby= still wins.
"""
from cc.base.db import database_connection_manager


def test_order_class_vars_declared():
    from cc.base.arm.common.base_entity import BaseEntity
    from cc.base.arm.project import Project
    from cc.base.arm.environment import Environment
    from cc.base.arm.version import Version
    from cc.base.arm.backup import Backup

    assert BaseEntity._order == "id"          # safe stable default
    assert Project._order == "name ASC"
    assert Environment._order == "name ASC"
    assert Version._order == "name ASC"
    assert Backup._order == "created_at DESC"  # snapshots: newest first


def test_find_by_returns_name_order_regardless_of_insertion(_db):
    from cc.base.arm.project import Project
    with database_connection_manager():
        for n in ("zeta", "alpha", "mid"):  # inserted out of order
            Project.create({"name": n})
        names = [p.name for p in Project.find_by()]
    assert names == ["alpha", "mid", "zeta"]


def test_search_honors_default_order(_db):
    from cc.base.arm.project import Project
    with database_connection_manager():
        for n in ("zeta", "alpha", "mid"):
            Project.create({"name": n})
        names = [p.name for p in Project.search([("id", ">", 0)])]
    assert names == ["alpha", "mid", "zeta"]


def test_explicit_orderby_overrides_default(_db):
    from cc.base.arm.project import Project
    with database_connection_manager():
        for n in ("zeta", "alpha", "mid"):
            Project.create({"name": n})
        names = [p.name for p in Project.find_by(orderby="name DESC")]
    assert names == ["zeta", "mid", "alpha"]
