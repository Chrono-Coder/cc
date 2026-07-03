"""
Setting service — application settings management.
"""
import logging

from cc.daemon.rpc_method import rpc_method

log = logging.getLogger("CC")


@rpc_method
def upsert(key: str, value: str) -> None:
    """Create or update a setting by key."""
    from cc.base.arm.setting import Setting
    from cc.base.db import database_connection_manager

    with database_connection_manager():
        existing = Setting.find_by(name=key, limit=1)
        if existing:
            existing.update({"value": value})
        else:
            Setting.create({"name": key, "value": value})
        log.debug(f"upsert: setting '{key}' = '{value}'")

    # PG connection settings changed — drop the cached connector/backend choice.
    if key in ("pg.connection", "pg.container"):
        from cc.services import pg_connect
        pg_connect.reset()


@rpc_method
def schema() -> list:
    """Return the declarative settings registry (cc.config.schema) so the web
    companion renders its settings form from the same source of truth the CLI
    (`cc config` / `cc setup`) uses — no more hand-kept duplication."""
    from cc.config.schema import settings as _settings

    out = []
    for entry in _settings():
        item = {"type": entry.get("type"), "label": entry.get("label")}
        if entry.get("type") != "section":
            item["key"] = entry.get("key")
            item["description"] = entry.get("description")
            if "default" in entry:
                item["default"] = entry["default"]
            if "options" in entry:
                item["options"] = entry["options"]
        out.append(item)
    return out
