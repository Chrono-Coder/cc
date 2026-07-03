"""
System service — introspection endpoints.

Exposes the full RPC schema derived from @rpc_method decorators.
Lazy-imports the router registry to avoid circular imports.
"""
import os
import time

from cc.daemon.rpc_method import _FUNCTION_REGISTRY, rpc_method
from cc.utils.constants import Constants


@rpc_method
def health() -> dict:
    """
    Return daemon runtime health stats.

    Response keys:
        version         — str, the running daemon's cc version
        uptime_seconds  — float, seconds since daemon start
        rpc_count       — int, successful RPC calls served
        last_error      — str | None, last unhandled exception (method: message)
        db_size_bytes   — int | None, size of cc_cli.db on disk
    """
    from cc.daemon.server import _started_at, _rpc_count, _last_error

    db_size = None
    try:
        db_size = os.path.getsize(Constants.SQLITE_DB_PATH)
    except OSError:
        pass

    return {
        "version": Constants.CC_VERSION,
        "uptime_seconds": time.time() - _started_at,
        "rpc_count": _rpc_count,
        "last_error": _last_error,
        "db_size_bytes": db_size,
    }


@rpc_method
def describe() -> dict:
    """
    Return the full schema of all registered RPC methods.

    Example response:
        {
          "env.delete": {
            "params": {"env_id": {"type": "int", "required": true}},
            "returns": "None"
          },
          "env.update": {
            "params": {
              "env_id": {"type": "int", "required": true},
              "**fields": {"type": "any", "required": false}
            },
            "returns": "None"
          },
          ...
        }
    """
    # Lazy imports to avoid circular dependency
    from cc.daemon.router import _REGISTRY
    from cc.base.arm.common.base_entity import _entity_registry
    from cc.base.arm.common.property import Property

    # Build field-name → semantic lookup from all ORM models.
    # Field names are consistent across models (e.g. all *_at fields are datetime),
    # so last-write-wins is safe here.
    field_semantics: dict[str, str] = {}
    for cls in _entity_registry:
        for attr_name, attr_val in vars(cls).items():
            if isinstance(attr_val, Property) and attr_val._semantic:
                field_semantics[attr_name] = attr_val._semantic

    schema = {}
    for namespace, module in _REGISTRY.items():
        for fn_name in dir(module):
            if fn_name.startswith("_"):
                continue
            fn = getattr(module, fn_name, None)
            if not (fn and callable(fn) and hasattr(fn, "_rpc_schema_key")):
                continue
            key = fn._rpc_schema_key
            if key not in _FUNCTION_REGISTRY:
                continue

            # Deep-copy the stored schema entry and enrich str params with semantics
            import copy
            entry = copy.deepcopy(_FUNCTION_REGISTRY[key])
            for param_name, param_info in entry["params"].items():
                if param_info.get("type") == "str" and param_name in field_semantics:
                    param_info["semantic"] = field_semantics[param_name]
            schema[f"{namespace}.{fn_name}"] = entry

    return dict(sorted(schema.items()))


@rpc_method
def describe_models() -> dict:
    """
    Return the schema of all ORM models — field types, semantics, and relations.

    Example response:
        {
          "environment": {
            "fields": {
              "name":         {"type": "str",      "required": true,  "unique": true},
              "last_used_at": {"type": "str",      "semantic": "datetime"},
              "github_url":   {"type": "str",      "semantic": "url"},
              "notes":        {"type": "str",      "semantic": "text"},
              "ticket_ids":   {"type": "str",      "semantic": "csv"},
              "project_path": {"type": "str",      "semantic": "path"},
              "project_id":   {"type": "many2one", "target": "project"},
              "module_ids":   {"type": "one2many", "target": "module", "inverse": "environment_id"}
            }
          },
          ...
        }
    """
    from cc.base.arm.common.base_entity import _entity_registry
    from cc.base.arm.common.property import Property

    models = {}
    for cls in _entity_registry:
        fields = {}
        for attr_name, attr_val in vars(cls).items():
            if not isinstance(attr_val, Property):
                continue
            if attr_val._one2many:
                fields[attr_name] = {
                    "type": "one2many",
                    "target": attr_val._one2many,
                    "inverse": attr_val._inverse_name,
                }
            elif attr_val._many2many:
                fields[attr_name] = {"type": "many2many", "target": attr_val._many2many}
            elif attr_val._relation:
                fields[attr_name] = {"type": "many2one", "target": attr_val._relation}
            else:
                entry: dict = {
                    "type": attr_val._type.__name__,
                    "required": bool(attr_val._required),
                    "unique": bool(attr_val._unique),
                }
                if attr_val._semantic:
                    entry["semantic"] = attr_val._semantic
                fields[attr_name] = entry
        models[cls._name] = {"fields": fields}

    return dict(sorted(models.items()))
