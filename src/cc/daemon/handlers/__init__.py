"""Core daemon-side event handlers. Imported by the daemon event bus's
``_ensure_loaded`` so their ``@on_event`` registrations run."""
from . import reindex  # noqa: F401  (registers the post-switch reindex handler)
