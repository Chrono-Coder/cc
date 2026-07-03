"""IDE writer plugin system.

cc keeps the "switch and your editor follows" workflow, but per-IDE writing
code lives behind a small plugin interface so:

1. cc core has no per-IDE branching.
2. New editors can be added by writing one file, not patching switch_command.
3. Third parties can ship writers via entry points or local drop-in files
   without forking cc.

Built-in writers: VSCode, Cursor. Anything else is a plugin.

See ``IdeWriter`` in :mod:`cc.ide.base` for the contract.
"""

from cc.ide.base import IdeWriter
from cc.ide.registry import active_writers, all_writers
from cc.ide.state import CcState
from cc.ide.vscode import CursorWriter, VSCodeWriter

__all__ = [
    "CcState",
    "CursorWriter",
    "IdeWriter",
    "VSCodeWriter",
    "active_writers",
    "all_writers",
]
