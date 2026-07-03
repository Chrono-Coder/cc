"""
RPC Router — dispatches method strings to service functions.

Rules:
- No DB access
- No transport awareness (no sockets, no JSON)
- No business logic
- Only routing: "namespace.function" → services/<namespace>.function()
"""
import dataclasses

from cc.services import backup, database, environment, intel, pg, project, setting, sync, system, timesheet, version, workspace

# Registry maps RPC namespace → service module.
# Add new namespaces here as services grow.
_REGISTRY = {
    "env": environment,
    "project": project,
    "workspace": workspace,
    "database": database,
    "timesheet": timesheet,
    "version": version,
    "backup": backup,
    "setting": setting,
    "system": system,
    "pg": pg,
    "sync": sync,
    "intel": intel,
}


class RPCError(Exception):
    """Raised when a method cannot be dispatched."""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def dispatch(method: str, params: dict):
    """
    Dispatch an RPC method call to the appropriate service function.

    Args:
        method: Dot-separated string — "namespace.function_name"
        params: Keyword arguments passed to the service function

    Returns:
        Whatever the service function returns (Python objects only)

    Raises:
        RPCError: If the method is unknown or the namespace is not registered
    """
    parts = method.split(".", 1)
    if len(parts) != 2:
        raise RPCError(-32600, f"Invalid method format: '{method}' — expected 'namespace.function'")

    namespace, fn_name = parts

    module = _REGISTRY.get(namespace)
    if module is None:
        raise RPCError(-32601, f"Unknown namespace: '{namespace}'")

    fn = getattr(module, fn_name, None)
    if fn is None or not callable(fn) or not hasattr(fn, "_rpc_required"):
        raise RPCError(-32601, f"Unknown method: '{method}'")

    # Validate required params against the signature recorded by @rpc_method
    for param_name, expected_type in fn._rpc_required.items():
        if param_name not in params:
            raise RPCError(-32602, f"Missing required param: '{param_name}'")
        if expected_type is not object and not isinstance(params[param_name], expected_type):
            actual = type(params[param_name]).__name__
            raise RPCError(-32602, f"'{param_name}' must be {expected_type.__name__}, got {actual}")

    result = fn(**params)

    # Serialize DTOs to plain dicts for transport
    if dataclasses.is_dataclass(result) and not isinstance(result, type):
        return dataclasses.asdict(result)

    if isinstance(result, list):
        return [
            dataclasses.asdict(item) if (dataclasses.is_dataclass(item) and not isinstance(item, type)) else item
            for item in result
        ]

    return result
