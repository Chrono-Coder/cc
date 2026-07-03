"""Core (in-tree) event handlers.

Importing this package registers every core handler via its ``@subscribe``
decorator.
"""

from cc.events.handlers import rnd  # noqa: F401  (registers the switch-rebase handler)
from cc.events.handlers import timesheet  # noqa: F401  (registers timesheet handlers)
