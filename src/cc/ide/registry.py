"""IDE writer discovery and selection."""

from __future__ import annotations

import importlib.util
import logging
from importlib.metadata import entry_points
from pathlib import Path

from cc.ide.base import IdeWriter

log = logging.getLogger("CC")

ENTRY_POINT_GROUP = "cc.ide_writers"
LOCAL_WRITERS_DIR = Path("~/.cc-cli/ide_writers").expanduser()


def _builtin_writers() -> list[IdeWriter]:
    # Local import keeps cc.ide.__init__ importable before submodules load.
    from cc.ide.vscode import CursorWriter, VSCodeWriter

    return [VSCodeWriter(), CursorWriter()]


def _entry_point_writers() -> list[IdeWriter]:
    writers: list[IdeWriter] = []
    try:
        eps = entry_points().select(group=ENTRY_POINT_GROUP)
    except Exception as e:
        log.debug(f"Could not enumerate entry points for {ENTRY_POINT_GROUP}: {e}")
        return writers
    for ep in eps:
        try:
            cls = ep.load()
        except Exception as e:
            log.warning(f"Failed to load IDE writer entry point {ep.name!r}: {e}")
            continue
        if not isinstance(cls, type) or not issubclass(cls, IdeWriter):
            log.warning(f"Entry point {ep.name!r} did not provide an IdeWriter subclass.")
            continue
        try:
            writers.append(cls())
        except Exception as e:
            log.warning(f"Failed to instantiate IDE writer {ep.name!r}: {e}")
    return writers


def _local_writers() -> list[IdeWriter]:
    writers: list[IdeWriter] = []
    if not LOCAL_WRITERS_DIR.exists():
        return writers
    for path in sorted(LOCAL_WRITERS_DIR.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"cc_ide_local_{path.stem}", path)
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            log.warning(f"Failed to load local IDE writer {path.name}: {e}")
            continue
        for attr in vars(mod).values():
            if (
                isinstance(attr, type)
                and issubclass(attr, IdeWriter)
                and attr is not IdeWriter
                and attr.__module__ == mod.__name__
            ):
                try:
                    writers.append(attr())
                except Exception as e:
                    log.warning(f"Failed to instantiate local IDE writer {attr.__name__}: {e}")
    return writers


def all_writers() -> list[IdeWriter]:
    """All available IDE writers: built-in + entry-point plugins + local files.

    Later writers override earlier ones if they share a ``name`` — this lets
    a user-shipped local plugin replace a built-in writer if they want.
    """
    by_name: dict[str, IdeWriter] = {}
    for w in _builtin_writers() + _entry_point_writers() + _local_writers():
        by_name[w.name] = w
    return list(by_name.values())


#: Maps legacy launcher-command values (used by ``cc project open``) to writer names.
#: Lets existing users with ``ide=code`` keep working without manual migration.
_LAUNCHER_TO_WRITER = {
    "code": "vscode",
    "cursor": "cursor",
    "vscode": "vscode",
}


def _read_ide_setting() -> str:
    """Return the resolved ``cc.ide`` writer-selection string.

    The ``ide`` setting historically holds the launcher command consumed by
    ``cc project open`` (``"code"`` / ``"cursor"`` / ``"pycharm"``). Those legacy
    values are normalized to writer names here so a single setting drives
    both ``cc project open`` (the launcher) and ``cc switch`` (the writer plugins).

    Special values that bypass the legacy mapping:
        * ``"auto"`` — auto-detect via each writer's :meth:`detect`.
        * ``"none"`` — no writers active.
        * Comma-separated writer names — explicit selection.

    Defaults to ``"auto"`` when no setting is configured.
    """
    try:
        from cc.base.arm.setting import Setting

        row = Setting.find_by(name="ide", limit=1)
        if row:
            value = (row[0].value or "").strip()
            if value:
                normalized = value.lower()
                if normalized in {"auto", "none"} or "," in normalized:
                    return value
                # Map legacy launcher names to writer names.
                return _LAUNCHER_TO_WRITER.get(normalized, value)
    except Exception as e:
        log.debug(f"Could not read cc.ide setting: {e}")
    return "auto"


def active_writers(workspace_path: Path) -> list[IdeWriter]:
    """Return the writers that should run for this workspace.

    Resolution order:

    * If ``cc.ide`` is ``"none"`` (case-insensitive), returns ``[]``.
    * If ``cc.ide`` is ``"auto"`` (the default), returns every writer whose
      ``detect()`` returns True.
    * Otherwise treats ``cc.ide`` as a comma-separated list of writer names
      and returns those, in order. Unknown names are warned and skipped.
    """
    setting = _read_ide_setting()
    normalized = setting.lower()

    if normalized == "none":
        return []

    available = {w.name: w for w in all_writers()}

    if normalized == "auto":
        return [w for w in available.values() if _safe_detect(w, workspace_path)]

    selected: list[IdeWriter] = []
    seen: set[str] = set()
    for raw in setting.split(","):
        name = raw.strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        if name not in available:
            log.warning(f"cc.ide references unknown writer {name!r}; skipping.")
            continue
        selected.append(available[name])
    return selected


def _safe_detect(writer: IdeWriter, workspace_path: Path) -> bool:
    try:
        return bool(writer.detect(workspace_path))
    except Exception as e:
        log.debug(f"IDE writer {writer.name} detect() failed: {e}")
        return False
