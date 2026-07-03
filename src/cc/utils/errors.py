class CCError(Exception):
    """Base class for all user-facing CC errors."""
    pass


class NotFoundError(CCError):
    """A requested resource does not exist."""
    pass


class ValidationError(CCError):
    """The operation is invalid given the current state."""
    pass


class ConflictError(CCError):
    """The operation would violate a uniqueness constraint."""
    pass


class DaemonError(CCError):
    """The daemon is unavailable or returned an unexpected error."""
    pass
