"""
@rpc_method decorator — marks a service function as RPC-callable, records its
required params for router validation, and registers its full schema for introspection.

Usage:
    from cc.daemon.rpc_method import rpc_method

    @rpc_method
    def delete(env_id: int) -> None:
        ...

At decoration time the decorator:
  1. Builds `_rpc_required` — required param → type, used by the router for validation.
  2. Populates `_FUNCTION_REGISTRY` with the full human-readable schema (all params +
     return type), keyed by "module.qualname". Used by `services/system.py` to serve
     the `system.describe` introspection endpoint.

Required = no default value, not *args / **kwargs.
Type hints drive isinstance validation; unannotated params accept any type ("any").
The router refuses to dispatch any function that has NOT been decorated.
"""
import inspect
from typing import Union, get_type_hints

# Global schema registry populated at module import time as each service is decorated.
# Key: "cc.services.environment.update"
# Value: {"params": {"env_id": {"type": "int", "required": True}, ...}, "returns": "None"}
_FUNCTION_REGISTRY: dict[str, dict] = {}


def _type_str(tp) -> str:
    """Convert a Python type annotation to a human-readable string."""
    if tp is object or tp is inspect.Parameter.empty:
        return "any"
    if tp is type(None):
        return "null"

    origin = getattr(tp, "__origin__", None)

    # Handle Union / Optional
    if origin is Union:
        args = tp.__args__
        non_none = [_type_str(a) for a in args if a is not type(None)]
        has_none = type(None) in args
        base = " | ".join(non_none)
        return f"{base} | null" if has_none else base

    # Handle list[X], dict[K, V], etc.
    if origin is list:
        inner_args = getattr(tp, "__args__", None)
        if inner_args:
            return f"list[{_type_str(inner_args[0])}]"
        return "list"
    if origin is dict:
        inner_args = getattr(tp, "__args__", None)
        if inner_args and len(inner_args) == 2:
            return f"dict[{_type_str(inner_args[0])}, {_type_str(inner_args[1])}]"
        return "dict"

    # Plain type with __name__ (int, str, bool, etc.)
    if hasattr(tp, "__name__"):
        return tp.__name__

    # Fallback for string annotations or anything else
    return str(tp).replace("typing.", "")


def rpc_method(func):
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    # --- Validation contract (used by router) ---
    required = {
        name: hints.get(name, object)
        for name, param in sig.parameters.items()
        if param.kind not in (param.VAR_POSITIONAL, param.VAR_KEYWORD)
        and param.default is inspect.Parameter.empty
    }
    func._rpc_required = required

    # --- Full schema (used by system.describe) ---
    params_schema: dict[str, dict] = {}
    for name, param in sig.parameters.items():
        if param.kind == param.VAR_KEYWORD:
            # **kwargs: show as open payload marker
            params_schema["**fields"] = {"type": "any", "required": False}
            continue
        if param.kind == param.VAR_POSITIONAL:
            continue
        is_required = param.default is inspect.Parameter.empty
        entry: dict = {
            "type": _type_str(hints.get(name, object)),
            "required": is_required,
        }
        if not is_required and param.default is not inspect.Parameter.empty and param.default is not None:
            entry["default"] = repr(param.default)
        params_schema[name] = entry

    schema_key = f"{func.__module__}.{func.__qualname__}"
    _FUNCTION_REGISTRY[schema_key] = {
        "params": params_schema,
        "returns": _type_str(hints.get("return", object)),
    }
    func._rpc_schema_key = schema_key

    return func
