"""
Theme picker + custom-color builder for cc.

Two interactive TUIs (built on prompt_toolkit) and the persistence
helper that ties theme selection to the daemon's setting table + the
rich Console + the prompter style.

Used by:
  - `cc config theme` (standalone command)
  - `cc config` wizard (the theme step)

Pure module — no Command-class dependency. Callers handle the
"where to fire it" — these functions just return the user's pick or
do the apply.
"""
import logging
import math
import sys

from prompt_toolkit.application import Application
from prompt_toolkit.cursor_shapes import CursorShape
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.dimension import Dimension
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.styles import DynamicStyle
from prompt_toolkit.widgets import Frame

from cc.daemon.client import call
from cc.utils.colors import CUSTOM_COLORS, THEMES
from cc.utils.console import apply_theme as apply_console_theme, get_console
from cc.utils.constants import Constants
from cc.utils.prompter.prompter import build_prompter_style, update_prompter_style

log = logging.getLogger("CC")


# ── Sample data shown in the preview panes ───────────────────────────


_SAMPLE_ENV = ("acme_memberships", "19.0-1234567-memberships-dev", "acme")
_SAMPLE_MODULES = "sale_management, account, approvals"
_RIGHT_W = 46


def _pt_color(val, fallback):
    """Convert palette PT_* value to a prompt_toolkit color string."""
    if not val:
        return fallback
    if val.startswith("ansi") or val.startswith("#"):
        return val
    return fallback


# ── Theme picker ──────────────────────────────────────────────────────


def pick_theme() -> str | None:
    """Show the named-theme picker. Returns theme name or None if cancelled."""
    theme_names = list(THEMES.keys())
    state = {"cursor": 0, "result": None}

    def _left():
        parts = []
        for i, name in enumerate(theme_names):
            palette = THEMES[name]
            pri = _pt_color(palette.get("PT_PRIMARY"), "ansicyan")
            is_cursor = i == state["cursor"]
            bar = ("class:pointer", " ▌ ") if is_cursor else ("class:col.label", " │ ")
            label_style = f"fg:{pri} bold" if is_cursor else ""
            parts += [bar, (label_style, f"{name:<12}"), ("", "\n")]
        return FormattedText(parts)

    def _right():
        palette = THEMES[theme_names[state["cursor"]]]
        pri = _pt_color(palette.get("PT_PRIMARY"), "ansicyan")
        sep = (f"fg:{pri}", " " + "─" * (_RIGHT_W - 2))
        env_name, branch, db = _SAMPLE_ENV
        return FormattedText([
            (f"fg:{pri} bold", f" {env_name}"), ("", "\n"),
            sep, ("", "\n"),
            (f"fg:{pri}", " Branch   "), ("", branch), ("", "\n"),
            (f"fg:{pri}", " DB       "), ("", db), ("", "\n"),
            (f"fg:{pri}", " Last     "), ("", "2d ago"), ("", "\n"),
            sep, ("", "\n"),
            (f"fg:{pri}", " Modules  "), ("", _SAMPLE_MODULES), ("", "\n"),
        ])

    def _dynamic_style():
        palette = THEMES[theme_names[state["cursor"]]]
        pri = _pt_color(palette.get("PT_PRIMARY"), "ansicyan")
        branch_c = _pt_color(palette.get("PT_BRANCH"), "ansiyellow")
        db_c = _pt_color(palette.get("PT_DB"), "#F4845F")
        sl_c = _pt_color(palette.get("PT_SLIDER"), branch_c)
        return build_prompter_style(primary=pri, branch=branch_c, db=db_c, slider=sl_c)

    layout = Layout(HSplit([
        VSplit([
            Frame(
                Window(FormattedTextControl(_left), width=18,
                       height=Dimension.exact(len(theme_names))),
                title=" theme ",
            ),
            Frame(
                Window(FormattedTextControl(_right),
                       height=Dimension.exact(max(len(theme_names), 8))),
                title=" preview ",
            ),
        ]),
        Window(FormattedTextControl(lambda: FormattedText([
            ("class:col.label", " ↑↓"), ("", " navigate"),
            ("class:col.label", "   ↵"), ("", " select"),
            ("class:col.label", "   esc"), ("", " cancel"),
        ])), height=1),
    ]))

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        if state["cursor"] > 0:
            state["cursor"] -= 1

    @kb.add("down")
    def _down(event):
        if state["cursor"] < len(theme_names) - 1:
            state["cursor"] += 1

    @kb.add("enter")
    def _select(event):
        state["result"] = theme_names[state["cursor"]]
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit()

    app = Application(
        layout=layout, key_bindings=kb,
        style=DynamicStyle(_dynamic_style),
        full_screen=False, cursor=CursorShape._NEVER_CHANGE,
    )
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()
    app.output.show_cursor = lambda: None
    app.run()
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()

    return state["result"]


# ── Custom color picker (per-role) ────────────────────────────────────


def _pick_custom_color(role: str, current: str, primary: str, slider: str) -> str | None:
    """Color picker for a single role. Preview shows all roles with
    only this one changing live. Returns the picked color name or None."""
    color_names = list(CUSTOM_COLORS.keys())
    start = color_names.index(current) if current in color_names else 0
    state = {"cursor": start, "result": None}

    n = len(color_names)
    rows = math.ceil(n / 2)

    def _get_colors():
        """Return (pri, sl) with the live selection applied to the active role."""
        live = CUSTOM_COLORS[color_names[state["cursor"]]]["pt"]
        p  = live if role == "primary" else CUSTOM_COLORS.get(primary, {}).get("pt", "ansicyan")
        sl = live if role == "slider"  else CUSTOM_COLORS.get(slider,  {}).get("pt", "ansiyellow")
        return p, sl

    def _left():
        parts = []
        half = math.ceil(n / 2)
        for row in range(half):
            for col in (0, 1):
                idx = row + col * half
                if idx >= n:
                    parts += [("", "                    ")]
                    continue
                name = color_names[idx]
                c = CUSTOM_COLORS[name]
                is_cur = idx == state["cursor"]
                bar = ("class:pointer", " ▌ ") if is_cur else (f"fg:{c['pt']}", " │ ")
                swatch = (f"fg:{c['pt']}", "███ ")
                label_s = f"fg:{c['pt']} bold" if is_cur else f"fg:{c['pt']}"
                parts += [bar, swatch, (label_s, f"{name:<10}")]
            parts += [("", "\n")]
        return FormattedText(parts)

    def _right():
        p, sl = _get_colors()
        sep = (f"fg:{p}", " " + "─" * (_RIGHT_W - 2))
        env_name, branch, db = _SAMPLE_ENV
        return FormattedText([
            (f"fg:{p} bold", f" {env_name}"), ("", "\n"),
            sep, ("", "\n"),
            (f"fg:{p}", " Branch   "), ("", branch), ("", "\n"),
            (f"fg:{p}", " DB       "), ("", db), ("", "\n"),
            (f"fg:{p}", " Last     "), ("", "2d ago"), ("", "\n"),
            sep, ("", "\n"),
            (f"fg:{p}", " Modules  "), ("", _SAMPLE_MODULES), ("", "\n"),
        ])

    def _dynamic_style():
        p, sl = _get_colors()
        return build_prompter_style(primary=p, branch=sl, db="#F4845F", slider=sl)

    layout = Layout(HSplit([
        VSplit([
            Frame(Window(FormattedTextControl(_left), width=44, height=Dimension.exact(rows)),
                  title=f" {role} "),
            Frame(Window(FormattedTextControl(_right), height=Dimension.exact(max(rows, 8))),
                  title=" preview "),
        ]),
        Window(FormattedTextControl(lambda: FormattedText([
            ("class:col.label", " ↑↓←→"), ("", " navigate"),
            ("class:col.label", "   ↵"), ("", " select"),
            ("class:col.label", "   esc"), ("", " cancel"),
        ])), height=1),
    ]))

    kb = KeyBindings()

    @kb.add("up")
    def _up(event):
        cur = state["cursor"]
        col = 0 if cur < rows else 1
        row = cur - col * rows
        if row > 0:
            state["cursor"] = (row - 1) + col * rows

    @kb.add("down")
    def _down(event):
        cur = state["cursor"]
        col = 0 if cur < rows else 1
        row = cur - col * rows
        if row + 1 < rows and cur + 1 < n:
            state["cursor"] = (row + 1) + col * rows

    @kb.add("left")
    def _left_kb(event):
        cur = state["cursor"]
        if cur >= rows:
            state["cursor"] = cur - rows

    @kb.add("right")
    def _right_kb(event):
        cur = state["cursor"]
        if cur < rows and cur + rows < n:
            state["cursor"] = cur + rows

    @kb.add("enter")
    def _sel(event):
        state["result"] = color_names[state["cursor"]]
        event.app.exit()

    @kb.add("escape")
    @kb.add("c-c")
    def _cancel(event):
        event.app.exit()

    app = Application(
        layout=layout, key_bindings=kb,
        style=DynamicStyle(_dynamic_style),
        full_screen=False, cursor=CursorShape._NEVER_CHANGE,
    )
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()
    app.output.show_cursor = lambda: None
    app.run()
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()
    return state["result"]


def pick_custom_colors(current_primary: str, current_slider: str) -> tuple[str, str] | None:
    """Run the two-step custom-color builder (primary then slider).
    Returns (primary, slider) or None if cancelled."""
    primary = _pick_custom_color("primary", current_primary, current_primary, current_slider)
    if not primary:
        return None
    slider = _pick_custom_color("slider", current_slider, primary, current_slider)
    if not slider:
        return None
    return primary, slider


# ── Persistence + application ─────────────────────────────────────────


def apply_named_theme(theme_name: str) -> None:
    """Apply a built-in theme: persist to settings, refresh rich + prompter."""
    if theme_name == "custom":
        raise ValueError("apply_custom_theme() must be used for the 'custom' theme")
    call("setting.upsert", key=Constants.SETTING_THEME, value=theme_name)
    apply_console_theme(theme_name)
    update_prompter_style(theme_name)
    get_console().print(f"  ✓ Theme → [primary]{theme_name}[/]")


def apply_custom_theme(primary: str, slider: str) -> None:
    """Apply the 'custom' theme with the picked primary + slider colors."""
    call("setting.upsert", key=Constants.SETTING_THEME_PRIMARY, value=primary)
    call("setting.upsert", key=Constants.SETTING_THEME_SLIDER, value=slider)
    call("setting.upsert", key=Constants.SETTING_THEME, value="custom")

    c = CUSTOM_COLORS
    THEMES["custom"].update({
        "PT_PRIMARY": c[primary]["pt"],
        "PT_SLIDER":  c[slider]["pt"],
    })

    primary_rich = c[primary]["rich"]
    slider_rich = c[slider]["rich"]
    apply_console_theme("custom", overrides={
        "primary": primary_rich,
        "heading": f"bold {primary_rich}",
        "header":  primary_rich,
    })
    update_prompter_style("custom")

    get_console().print(
        f"  ✓ Custom theme → "
        f"[{primary_rich}]primary:{primary}[/]  "
        f"[{slider_rich}]slider:{slider}[/]"
    )


def get_current_custom_colors() -> tuple[str, str]:
    """Return (primary, slider) color names from saved settings, with defaults."""
    # Read directly via daemon RPC — kept here so the picker module
    # is self-sufficient and doesn't push DB state into callers.
    from cc.base.arm.setting import Setting
    s_primary = Setting.find_by(name=Constants.SETTING_THEME_PRIMARY, limit=1)
    s_slider = Setting.find_by(name=Constants.SETTING_THEME_SLIDER, limit=1)
    cur_primary = (s_primary.value if s_primary else None) or "cyan"
    cur_slider = (s_slider.value if s_slider else None) or cur_primary
    return cur_primary, cur_slider


def run_theme_picker() -> bool:
    """Full flow: pick theme, then if 'custom' run the color builder, apply.
    Returns True if a theme was applied, False if cancelled."""
    chosen = pick_theme()
    if not chosen:
        return False
    if chosen == "custom":
        current_primary, current_slider = get_current_custom_colors()
        result = pick_custom_colors(current_primary, current_slider)
        if not result:
            return False
        primary, slider = result
        apply_custom_theme(primary, slider)
        return True
    apply_named_theme(chosen)
    return True
