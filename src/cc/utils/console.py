"""
Themed Rich console for cc.

Module-level Console singleton with semantic styles. Themes live in
PALETTES — each maps semantic names (primary, branch, db, success,
warning, error, muted, header, info, bg_accent) to rich styles.

Consumers should call get_console() and use markup:

    from cc.utils.console import get_console
    c = get_console()
    c.print("[primary]Active:[/] [branch]19.0-feature-x[/]")

Prompt-toolkit colors (PT_*) still live in cc.utils.colors — rich
only handles output rendering, not the interactive prompter.
"""
from rich.console import Console
from rich.theme import Theme

PALETTES: dict[str, dict[str, str]] = {
    "default": {
        "primary":   "cyan",
        "heading":   "bold cyan",
        "branch":    "yellow",
        "db":        "white",
        "success":   "green",
        "warning":   "yellow",
        "error":     "red",
        "muted":     "grey78",
        "header":    "magenta",
        "info":      "blue",
        "bg_accent": "black on cyan",
    },
    "purple": {
        "primary":   "#a78bfa",
        "heading":   "bold #a78bfa",
        "branch":    "#fde047",
        "db":        "#fde047",
        "success":   "green",
        "warning":   "#fde047",
        "error":     "red",
        "muted":     "grey78",
        "header":    "#7c3aed",
        "info":      "blue",
        "bg_accent": "white on #6d28d9",
    },
    "chronocoder": {
        "primary":   "#FFCC00",
        "heading":   "bold #FFCC00",
        "branch":    "#C41E3A",
        "db":        "#C41E3A",
        "success":   "green",
        "warning":   "#FFCC00",
        "error":     "red",
        "muted":     "#FFCC00",
        "header":    "#8C1423",
        "info":      "#78283C",
        "bg_accent": "#FFCC00 on #782838",
    },
    "custom": {
        "primary":   "cyan",
        "heading":   "bold cyan",
        "branch":    "yellow",
        "db":        "#F4845F",
        "success":   "green",
        "warning":   "yellow",
        "error":     "red",
        "muted":     "grey78",
        "header":    "cyan",
        "info":      "blue",
        "bg_accent": "black on cyan",
    },
}

_console: Console | None = None
_error_console: Console | None = None
_active_theme: str = "default"
_active_overrides: dict[str, str] | None = None


def _build_console(
    theme_name: str, overrides: dict[str, str] | None = None, *, stderr: bool = False
) -> Console:
    palette = dict(PALETTES.get(theme_name, PALETTES["default"]))
    if overrides:
        palette.update(overrides)
    return Console(theme=Theme(palette), stderr=stderr)


def get_console() -> Console:
    """Return the themed stdout Console singleton, creating it on first use."""
    global _console
    if _console is None:
        _console = _build_console(_active_theme, _active_overrides)
    return _console


def get_error_console() -> Console:
    """Return the themed Console singleton bound to stderr.

    Diagnostics (errors, warnings) go here so command stdout stays a clean,
    pipeable data stream. Same theme as get_console(); only the stream differs.
    """
    global _error_console
    if _error_console is None:
        _error_console = _build_console(_active_theme, _active_overrides, stderr=True)
    return _error_console


def apply_theme(name: str, overrides: dict[str, str] | None = None) -> None:
    """Switch the active theme. Falls back to 'default' for unknown names.

    `overrides` lets the caller swap individual palette keys (used by the
    'custom' theme to inject the user's picked primary/slider colors from
    settings).
    """
    global _console, _error_console, _active_theme, _active_overrides
    _active_theme = name if name in PALETTES else "default"
    _active_overrides = overrides
    _console = _build_console(_active_theme, _active_overrides)
    _error_console = _build_console(_active_theme, _active_overrides, stderr=True)


def active_theme() -> str:
    """Name of the currently applied theme."""
    return _active_theme


def available_themes() -> list[str]:
    return list(PALETTES.keys())
