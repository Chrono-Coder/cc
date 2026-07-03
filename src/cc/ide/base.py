"""IDE writer plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import ClassVar

from cc.ide.state import CcState


class IdeWriter(ABC):
    """Plugin interface for writing cc state into an editor's native config.

    Two phases:

    * ``setup(workspace_path)`` runs **once per workspace** (during
      ``cc workspace add`` or via an explicit ``cc config ide setup`` call). It writes
      stable artifacts that reference cc state through indirection — for
      VSCode, that's the ``launch.json`` template whose entries reference
      ``${config:cc.*}`` keys that live in ``settings.json``.

    * ``apply(workspace_path, state)`` runs **on every ``cc switch``**. It
      only touches the per-switch dynamic state — for VSCode, that's the
      ``cc.*`` keys in ``settings.json`` plus the python interpreter path.
      **It MUST NOT touch ``launch.json`` (or its per-IDE equivalent).** That
      protects user customizations from being overwritten on every switch.

    Implementations should be idempotent: running ``apply()`` twice with the
    same state must produce the same files. Writes should be merge-safe —
    never blindly overwrite a file the user may have edited.
    """

    #: Short, lowercase identifier (e.g. ``"vscode"``). Must be unique across
    #: all registered writers. Used as the key in the ``cc.ide`` setting.
    name: ClassVar[str]

    @abstractmethod
    def detect(self, workspace_path: Path) -> bool:
        """Return True if this IDE is in use in the given workspace.

        Should be a cheap filesystem check (e.g. presence of ``.vscode/``).
        No RPC, no heavy IO. Used during auto-detection when ``cc.ide`` is
        set to ``"auto"`` (the default).
        """

    @abstractmethod
    def setup(self, workspace_path: Path) -> None:
        """Write one-time artifacts (debugger templates, etc.) for this IDE.

        Called from ``cc workspace add`` and ``cc config ide setup``. Never called
        from ``cc switch``.
        """

    @abstractmethod
    def apply(self, workspace_path: Path, state: CcState) -> None:
        """Project the given cc state into the IDE's per-switch config.

        Called from ``cc switch`` after the active environment changes.
        Must NOT touch any template / launch / run-config files written by
        ``setup()`` — those are protected from per-switch updates.
        """
