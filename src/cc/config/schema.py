"""
Declarative settings registry for cc.

Single source of truth describing every cc setting: its key, label,
human description, type, and optional auto-detect callable. Consumed
by the `cc setup` wizard (iterates this list) and `cc config` picker
(renders + validates against it).

`{"type": "section", ...}` entries are visual headers in the wizard,
not actual settings.
"""
from typing import Any

from cc.utils.constants import Constants


def settings() -> list[dict[str, Any]]:
    """Return the settings registry — call-site `Constants` references
    are resolved at runtime so an import order swap can't break this.
    Plugin-contributed entries (`cc.settings` group) are appended."""
    registry: list[dict[str, Any]] = [
        {"type": "section", "label": "General"},
        {
            "key": "download",
            "label": "Dump files directory",
            "description": "Where CC looks for database dump files (cc db init). Usually ~/Downloads.",
            "type": "path",
            "auto_detect": "_detect_download_path",
        },
        {
            "key": "ide",
            "label": "IDE",
            "description": (
                "Which editor to open and configure on switch. "
                "Drives both `cc project open` (the launcher) and `cc switch` "
                "(the writer plugins that update settings.json etc.). "
                "Auto-detect picks any writer whose detect() returns true."
            ),
            "type": "select",
            "options": {
                "Auto-detect": "auto",
                **Constants.IDE_MAP,
                "None (no editor integration)": "none",
            },
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_INTERNAL_ADDONS,
            "label": "Internal addons directory",
            "description": (
                "Name of a shared-addons directory probed inside each project root "
                "(e.g. a company-wide modules repo checked out into every project). "
                "Found dirs are appended to the addons path and their modules appear "
                "in pickers. Leave blank if you don't use one."
            ),
            "type": "str",
            "default": "",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_CLEAN_WORDS,
            "label": "Fuzzy-match clean words",
            "description": (
                "Extra comma-separated words stripped from names during fuzzy "
                "matching (dump files, project lookup). Example: acme,client."
            ),
            "type": "str",
            "default": "",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_TICKET_URL,
            "label": "Ticket URL template",
            "description": (
                "URL opened by `cc ticket`, with {ticket} as the placeholder. "
                "Blank uses the default (Odoo project app)."
            ),
            "type": "str",
            "default": "",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_RUNBOT_URL,
            "label": "Runbot URL template",
            "description": (
                "URL opened by `cc psx`, with {branch} as the placeholder. "
                "Blank uses the default (Odoo PS runbot)."
            ),
            "type": "str",
            "default": "",
            "auto_detect": None,
        },
        {"type": "section", "label": "Workspace"},
        {
            "key": Constants.SETTING_MULTI_VERSION,
            "label": "Multi-version mode",
            "description": (
                "Track a separate active project per Odoo version. "
                "Enable if you run v17 and v18 side by side in different terminals."
            ),
            "type": "bool",
            "auto_detect": None,
        },
        {"type": "section", "label": "Background Updates"},
        {
            "key": Constants.SETTING_AUTO_FETCH,
            "label": "Auto-fetch Odoo repos",
            "description": (
                "On switch, run git fetch in the background if the fetch interval has elapsed "
                "(default 24h). Keeps branches up to date without blocking the switch."
            ),
            "type": "bool",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_AUTO_FETCH_INTERVAL,
            "label": "Fetch interval (hours)",
            "description": "Minimum hours between background fetches per version.",
            "type": "int",
            "default": "24",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_RND_AUTO_REBASE,
            "label": "Auto-rebase R&D branches on switch",
            "description": (
                "In an R&D workspace, check out + rebase the env's branch across the shared "
                "Odoo repos on every switch. Off to switch without touching git."
            ),
            "type": "bool",
            "default": "true",
            "auto_detect": None,
        },
        {"type": "section", "label": "Environments"},
        {
            "key": Constants.SETTING_ENV_AUTO_STALE_DAYS,
            "label": "Auto-stale envs after (days)",
            "description": (
                "On switch, automatically mark active environments that haven't been "
                "used in this many days as merged/archived, so the switch picker stays "
                "short. Pinned envs are never touched. 0 disables."
            ),
            "type": "int",
            "default": "0",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_ENV_AUTO_STALE_STATUS,
            "label": "Auto-stale status",
            "description": (
                "Which status to apply when auto-staling. 'archived' hides until you "
                "reactivate; 'merged' can reappear if used again within the grace window."
            ),
            "type": "select",
            "options": {
                "Archived — hidden until reactivated": "archived",
                "Merged — soft, reappears if used again": "merged",
            },
            "default": "archived",
            "auto_detect": None,
        },
        {"type": "section", "label": "Timesheet"},
        {
            "key": Constants.SETTING_TIMESHEET_MODE,
            "label": "Tracking mode",
            "description": (
                "auto: log a time entry on every switch (default). "
                "manual: switches aren't tracked — only `cc time start/end` entries count."
            ),
            "type": "select",
            "options": {"Auto (log on switch)": "auto", "Manual (only cc time start/end)": "manual"},
            "default": "auto",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_TIMESHEET_THRESHOLD,
            "label": "Flag threshold (minutes)",
            "description": "Sessions longer than this are flagged with ⚑ when you switch away.",
            "type": "int",
            "default": "60",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_TIMESHEET_PROMPT,
            "label": "Prompt on flagged switch",
            "description": "Show a confirmation prompt when switching away from a long session.",
            "type": "bool",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_TIMESHEET_EOD,
            "label": "EOD auto-stop time",
            "description": (
                "Automatically punch out at this time if you forget. "
                "Format: HH:MM (e.g. 18:30). Leave blank to disable."
            ),
            "type": "str",
            "default": "",
            "auto_detect": None,
        },
        {
            "key": Constants.SETTING_TIMESHEET_RETENTION_DAYS,
            "label": "Switch-log retention (days)",
            "description": (
                "Prune switch-log entries older than this many days on switch. "
                "0 keeps history forever. Default 90."
            ),
            "type": "int",
            "default": "90",
            "auto_detect": None,
        },
        {"type": "section", "label": "Intel"},
        {
            "key": "intel.auto_reindex",
            "label": "Auto-reindex on switch",
            "description": (
                "Background-reindex the project's git repo on cc switch "
                "if it's a registered Intel repo and was last indexed >1h ago."
            ),
            "type": "bool",
            "default": "true",
            "auto_detect": None,
        },
        {"type": "section", "label": "Appearance"},
        {
            "key": Constants.SETTING_THEME,
            "label": "Color theme",
            "description": "Color palette used across all CC output and prompts.",
            "type": "theme",
            "auto_detect": None,
        },
    ]
    return registry


def known_keys() -> set[str]:
    """All valid setting keys (excludes section headers)."""
    return {s["key"] for s in settings() if s.get("type") != "section"}


def find(key: str) -> dict | None:
    """Return the settings entry for `key`, or None if not registered."""
    for s in settings():
        if s.get("key") == key:
            return s
    return None
