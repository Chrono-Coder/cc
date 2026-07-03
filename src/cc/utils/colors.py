"""
prompt_toolkit color palettes used by the interactive prompter.

rich-rendered output lives in cc.utils.console — these PT_* values are
only consumed by prompt_toolkit widgets (selectors, autocomplete, etc.)
via cc.utils.prompter.prompter.build_prompter_style().
"""

THEMES = {
    "default": {
        "PT_PRIMARY": "ansicyan",
        "PT_BRANCH":  "#fde047",
        "PT_DB":      "ansiwhite",
        "PT_SLIDER":  "ansicyan",
    },
    "purple": {
        "PT_PRIMARY": "#a78bfa",
        "PT_BRANCH":  "#fde047",
        "PT_DB":      "#fde047",
        "PT_SLIDER":  "#a78bfa",
    },
    "chronocoder": {
        "PT_PRIMARY": "#FFCC00",
        "PT_BRANCH":  "#C41E3A",
        "PT_DB":      "#C41E3A",
        "PT_SLIDER":  "#FFCC00",
    },
    "custom": {
        "PT_PRIMARY": "ansicyan",
        "PT_BRANCH":  "ansiyellow",
        "PT_DB":      "#F4845F",
        "PT_SLIDER":  "ansicyan",
    },
}


# Named colors offered by the custom-theme picker.
#   pt   — prompt_toolkit color string for the selectors
#   rich — same shade rendered through rich (matches Colors when the
#          terminal palette ANSI \033[91m etc. differs from a literal hex)
CUSTOM_COLORS = {
    "cyan":     {"pt": "ansicyan",    "rich": "bright_cyan"},
    "magenta":  {"pt": "ansimagenta", "rich": "bright_magenta"},
    "yellow":   {"pt": "ansiyellow",  "rich": "bright_yellow"},
    "green":    {"pt": "ansigreen",   "rich": "bright_green"},
    "blue":     {"pt": "#29B6F6",     "rich": "#29B6F6"},
    "red":      {"pt": "ansired",     "rich": "bright_red"},
    "white":    {"pt": "ansiwhite",   "rich": "bright_white"},
    "lavender": {"pt": "#B388FF",     "rich": "#B388FF"},
    "coral":    {"pt": "#F4845F",     "rich": "#F4845F"},
    "mint":     {"pt": "#98FFCB",     "rich": "#98FFCB"},
    "sky":      {"pt": "#87CEEB",     "rich": "#87CEEB"},
    "rose":     {"pt": "#FF9CAC",     "rich": "#FF9CAC"},
    "peach":    {"pt": "#FFCBA4",     "rich": "#FFCBA4"},
    "lilac":    {"pt": "#DDA0DD",     "rich": "#DDA0DD"},
}


def available_themes() -> list[str]:
    """Theme names exposed to the picker."""
    return list(THEMES.keys())
