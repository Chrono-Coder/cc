"""VSCode + Cursor IDE writers.

These two editors share the same ``.vscode/`` config format — the writers
produce identical files. They're split into two classes only so users can
distinguish them in the ``cc.ide`` setting and so future Cursor-specific
behavior has a home without polluting the VSCode writer.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from cc.ide.base import IdeWriter
from cc.ide.state import CcState
from cc.utils.constants import Constants

log = logging.getLogger("CC")

VSCODE_DIR = ".vscode"
LAUNCH_FILE = "launch.json"
SETTINGS_FILE = "settings.json"


class VSCodeWriter(IdeWriter):
    """Writes cc state into ``.vscode/`` config files.

    * ``setup()`` merges cc's debug configurations from
      ``cc/templates/launch_template.json`` into ``launch.json``.
    * ``apply()`` writes the per-switch ``cc.*`` keys and the python
      interpreter path into ``settings.json``. Never touches ``launch.json``.
    """

    name = "vscode"

    def detect(self, workspace_path: Path) -> bool:
        if (workspace_path / VSCODE_DIR).is_dir():
            return True
        return os.environ.get("TERM_PROGRAM") == "vscode"

    def setup(self, workspace_path: Path) -> None:
        vscode_dir = workspace_path / VSCODE_DIR
        vscode_dir.mkdir(parents=True, exist_ok=True)
        launch_path = vscode_dir / LAUNCH_FILE

        template = self._read_template()
        if template is None:
            log.error(
                f"Failed to read launch template from: {Constants.TEMPLATE_LAUNCH_JSON_PATH}"
            )
            return

        existing = self._read_json(launch_path) or {
            "version": "0.2.0",
            "configurations": [],
            "inputs": [],
        }

        cc_config_names = {c.get("name") for c in template.get("configurations", [])}
        configurations = [
            c for c in existing.get("configurations", []) if c.get("name") not in cc_config_names
        ]
        configurations.extend(template.get("configurations", []))
        existing["configurations"] = configurations

        cc_input_ids = {i.get("id") for i in template.get("inputs", [])}
        inputs = [i for i in existing.get("inputs", []) if i.get("id") not in cc_input_ids]
        inputs.extend(template.get("inputs", []))
        existing["inputs"] = inputs

        self._write_json(launch_path, existing)
        log.debug(f"[ide:{self.name}] setup wrote launch templates → {launch_path}")

    def apply(self, workspace_path: Path, state: CcState) -> None:
        vscode_dir = workspace_path / VSCODE_DIR
        vscode_dir.mkdir(parents=True, exist_ok=True)
        settings_path = vscode_dir / SETTINGS_FILE

        settings = self._read_json(settings_path) or {}

        # Per-switch cc.* keys. Each is only set if the source value is present —
        # an empty value is treated as "do not write this key" (see CcState docstring).
        merges: dict[str, str] = {
            "cc.odooBin": state.odoo_bin,
            "cc.port": state.port,
            "cc.database": state.db,
            "cc.addonsPath": state.addons_path,
            "cc.modules": state.modules,
            "cc.upgradePath": state.upgrade_path,
            "cc.projectPath": state.project_path,
            "cc.envName": state.env_name,
            "cc.projectName": state.project_name,
        }
        for key, value in merges.items():
            if value:
                settings[key] = value
        settings.setdefault("cc.initMode", "-u")

        if state.python_path:
            settings["python.defaultInterpreterPath"] = state.python_path

        self._write_json(settings_path, settings)
        log.debug(f"[ide:{self.name}] apply wrote {settings_path}")

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError):
            log.debug(f"[ide:vscode] {path} exists but is empty/invalid — starting fresh.")
            return None
        except Exception as e:
            log.warning(f"[ide:vscode] could not read {path}: {e}")
            return None

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.warning(f"[ide:vscode] could not write {path}: {e}")

    def _read_template(self) -> dict | None:
        return self._read_json(Path(Constants.TEMPLATE_LAUNCH_JSON_PATH))


class CursorWriter(VSCodeWriter):
    """Cursor uses the same ``.vscode/`` format as VSCode — identical output.

    Auto-detection only fires on an explicit Cursor signal (env vars set by
    the Cursor IDE). If absent, VSCodeWriter wins by default and Cursor users
    can force this writer via ``cc.ide = cursor``.
    """

    name = "cursor"

    def detect(self, workspace_path: Path) -> bool:
        # Cursor sets TERM_PROGRAM=vscode for VSCode-compat. Distinguish via
        # Cursor-specific env vars when running inside its integrated terminal.
        if any(key.startswith("CURSOR_") for key in os.environ):
            return True
        return False
