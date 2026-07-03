"""
Inline two-pane environment selector — Direction C design.

Left pane: env names (project prefix stripped), slider on selected row.
Right pane: full env name as header, inner separator, details, then modules.

  ╭ acme ──────────────╮╭ acme_approvals ──────────────────────────────╮
  │ ▌ approvals        ││                                               │
  │   hr_expense       ││  Branch   19.0-1234567-approvals-dev          │
  │   memberships      ││  DB       acme_approvals                      │
  │   pos_internal     ││  Last     2d ago                              │
  │                    ││  ────────────────────────────────────         │
  │                    ││  Modules                                      │
  │                    ││  • sale_management                            │
  │                    ││  • approvals                                  │
  ╰────────────────────╯╰───────────────────────────────────────────────╯
    ↑↓ navigate   ↵ select   esc cancel
"""

import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from prompt_toolkit.application import Application
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame


class EnvSelectorTUI:
    LEFT_WIDTH = 32
    RIGHT_MIN_WIDTH = 52

    def __init__(
        self,
        environments: List[Any],
        project_name: str = "",
        active_env_id: Optional[int] = None,
        style: Optional[Style] = None,
        viewport: int = 10,
    ):
        self.environments = list(environments)
        self.project_name = project_name
        self.active_env_id = active_env_id
        self.style = style
        # How many rows the list shows at once. The full set stays available —
        # typing filters across all of it (cap = initial view, not reach).
        self.viewport = max(3, viewport)
        self.filter = ""
        # Open with the cursor on the active env (not always the top row), so
        # the common "re-confirm where I am" case is a single Enter.
        self.cursor = next(
            (i for i, e in enumerate(self.environments)
             if active_env_id and getattr(e, "id", None) == active_env_id),
            0,
        )
        self.result = None
        self._app: Optional[Application] = None

        # Module cache: env_id -> list[str] | None (None = loading)
        self._modules: Dict[int, Optional[List[str]]] = {}

    # ── filtering / windowing ───────────────────────────────────────────────────

    def _filtered(self) -> List[Any]:
        """Envs matching the current type-to-filter (case-insensitive substring).

        Searches the FULL set, not just the rows currently on screen."""
        if not self.filter:
            return self.environments
        f = self.filter.lower()
        return [e for e in self.environments if f in e.name.lower()]

    def _window(self, n: int) -> tuple:
        """(start, end) slice of the filtered list to render, centred on cursor."""
        if n <= self.viewport:
            return 0, n
        start = max(0, min(self.cursor - self.viewport // 2, n - self.viewport))
        return start, start + self.viewport

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _time_ago(iso_str: Optional[str]) -> str:
        if not iso_str:
            return "never"
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            secs = int((datetime.now(timezone.utc) - dt).total_seconds())
            if secs < 60:
                return "just now"
            if secs < 3600:
                return f"{secs // 60}m ago"
            if secs < 86400:
                return f"{secs // 3600}h ago"
            return f"{secs // 86400}d ago"
        except Exception:
            return "—"

    @staticmethod
    def _trunc(s: str, n: int) -> str:
        return s if len(s) <= n else s[: n - 1] + "…"

    def _fetch_modules(self, env_id: int) -> None:
        """Fetch modules for env_id in a background thread, then invalidate."""
        from cc.daemon.client import call
        try:
            modules = call("env.get_env_modules", env_id=env_id)
        except Exception:
            modules = []
        self._modules[env_id] = modules or []
        if self._app and self._app.is_running:
            self._app.invalidate()

    def _ensure_modules(self, env_id: int) -> None:
        """Start background fetch if not already fetched/fetching."""
        if env_id not in self._modules:
            self._modules[env_id] = None  # mark as loading
            t = threading.Thread(target=self._fetch_modules, args=(env_id,), daemon=True)
            t.start()

    # ── panel renderers ───────────────────────────────────────────────────────

    def _left_panel(self) -> FormattedText:
        items = self._filtered()
        if not items:
            return FormattedText([("class:col.label", " (no matches)")])

        parts = []
        max_w = self.LEFT_WIDTH - 5  # bar(3) + marker(2)
        start, end = self._window(len(items))
        for i in range(start, end):
            env = items[i]
            is_cursor = i == self.cursor
            is_active = bool(self.active_env_id and env.id == self.active_env_id)

            # Restrained badges: pin + non-active status, muted, to the right.
            status = getattr(env, "status", "active") or "active"
            bits = []
            if getattr(env, "pinned", False):
                bits.append("⚲")
            if status != "active":
                bits.append(status)
            suffix = ("  " + " ".join(bits)) if bits else ""

            name_w = max(6, max_w - len(suffix))
            name = self._trunc(env.name, name_w)
            bar = ("class:pointer", " ▌ ") if is_cursor else ("class:col.label", " │ ")
            name_style = "class:col.main" if is_cursor else ""
            marker = ("class:col.accent", " ✦") if is_active else ("", "  ")

            parts += [
                bar, (name_style, f"{name:<{name_w}}"),
                ("class:col.label", suffix), marker, ("", "\n"),
            ]

        return FormattedText(parts)

    def _right_panel(self) -> FormattedText:
        items = self._filtered()
        if not items:
            return FormattedText([("class:col.label", " no matching environments")])

        env = items[self.cursor]
        self._ensure_modules(env.id)

        branch = env.branch_name or "—"
        db = env.database or "—"
        last_used = self._time_ago(getattr(env, "last_used_at", None))

        self._ensure_modules(env.id)

        label = "class:col.label"
        sep = "class:col.label"

        rows: list = []
        # Env name header
        rows += [("class:col.main", f" {env.name}"), ("", "\n")]
        rows += [(sep, " " + "─" * (self.RIGHT_MIN_WIDTH - 2)), ("", "\n")]
        # Details
        rows += [(label, " Branch   "), ("", branch), ("", "\n")]
        rows += [(label, " DB       "), ("", db), ("", "\n")]
        rows += [(label, " Last     "), ("", last_used), ("", "\n")]
        rows += [(sep, " " + "─" * (self.RIGHT_MIN_WIDTH - 2)), ("", "\n")]
        # Modules
        modules = self._modules.get(env.id)
        if modules is None:
            rows += [(label, " Modules  "), ("", "loading…"), ("", "\n")]
        elif not modules:
            rows += [(label, " Modules  "), ("", "—"), ("", "\n")]
        else:
            rows += [(label, " Modules  "), ("", ", ".join(modules)), ("", "\n")]

        return FormattedText(rows)

    def _footer(self) -> FormattedText:
        items = self._filtered()
        n, total = len(items), len(self.environments)
        pos = f"  {self.cursor + 1}/{n}" if n else "  0"
        count = pos if n == total else f"{pos} of {total}"
        parts = [
            ("class:col.label", " ↑↓"), ("", " nav"),
            ("class:col.label", "  ↵"), ("", " select"),
            ("class:col.label", "  esc"), ("", " cancel"),
            ("class:col.label", "  type"), ("", " filter"),
            ("class:col.label", count),
        ]
        if self.filter:
            parts += [("", "   "), ("class:col.accent", f"/{self.filter}")]
        return FormattedText(parts)

    # ── run ───────────────────────────────────────────────────────────────────

    def run(self) -> Optional[Any]:
        if not self.environments:
            return None

        import shutil
        cols, rows = shutil.get_terminal_size((80, 24))

        # Frame height: enough for the right detail panel (~8) but capped to the
        # viewport so a big env set stays calm. The list itself shows at most
        # `viewport` rows (windowed); filtering reaches the whole set regardless.
        view_h = min(max(self.viewport, 8), max(rows - 4, 4))

        # Adaptive: if terminal is too narrow for two panes, use single pane
        min_two_pane = self.LEFT_WIDTH + self.RIGHT_MIN_WIDTH + 4
        use_single_pane = cols < min_two_pane

        if use_single_pane:
            left_w = max(cols - 4, 20)
            layout = Layout(
                HSplit([
                    Frame(
                        Window(
                            FormattedTextControl(self._left_panel),
                            width=left_w,
                            height=Dimension.exact(view_h),
                        ),
                        title=f" {self.project_name} ",
                    ),
                    Window(FormattedTextControl(self._footer), height=1),
                ])
            )
        else:
            layout = Layout(
                HSplit([
                    VSplit([
                        Frame(
                            Window(
                                FormattedTextControl(self._left_panel),
                                width=self.LEFT_WIDTH,
                                height=Dimension.exact(view_h),
                            ),
                            title=f" {self.project_name} ",
                        ),
                        Frame(
                            Window(
                                FormattedTextControl(self._right_panel),
                                height=Dimension.exact(view_h),
                            ),
                            title="",
                        ),
                    ]),
                    Window(FormattedTextControl(self._footer), height=1),
                ])
            )

        kb = KeyBindings()

        @kb.add("up")
        def _up(event):
            items = self._filtered()
            if items and self.cursor > 0:
                self.cursor -= 1
                self._ensure_modules(items[self.cursor].id)

        @kb.add("down")
        def _down(event):
            items = self._filtered()
            if items and self.cursor < len(items) - 1:
                self.cursor += 1
                self._ensure_modules(items[self.cursor].id)

        @kb.add("enter")
        def _select(event):
            items = self._filtered()
            if items:
                self.result = items[self.cursor]
            event.app.exit()

        @kb.add("escape")
        @kb.add("c-c")
        def _cancel(event):
            event.app.exit()

        @kb.add("backspace")
        def _backspace(event):
            if self.filter:
                self.filter = self.filter[:-1]
                self.cursor = 0

        @kb.add(Keys.Any)
        def _type(event):
            ch = event.data
            if ch and len(ch) == 1 and ch.isprintable():
                self.filter += ch
                self.cursor = 0
                items = self._filtered()
                if items:
                    self._ensure_modules(items[0].id)

        app = Application(
            layout=layout,
            key_bindings=kb,
            style=self.style,
            full_screen=False,
            cursor=CursorShape._NEVER_CHANGE,
        )
        self._app = app

        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()
        app.output.show_cursor = lambda: None
        try:
            app.run()
        finally:
            sys.stdout.write("\x1b[?25h")
            sys.stdout.flush()
            app.renderer.erase()

        return self.result
