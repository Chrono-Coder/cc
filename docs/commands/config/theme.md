# cc config theme

Pick or set the cc color theme.

## Usage

```bash
cc config theme                # interactive picker with live preview
cc config theme purple         # set directly to 'purple' (skip picker)
cc config theme custom         # open the custom-color builder
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Theme name. One of: `default`, `purple`, `chronocoder`, `custom`. Omit to open the picker. |

## Behavior

**Picker mode** (no args): two-pane TUI. Left pane lists themes; right pane shows a live preview of how `cc stat` renders under the highlighted theme. Arrow keys to navigate, Enter to select.

**Direct mode** (with name): sets the theme without the picker. Useful for scripting / dotfile init.

**Custom theme**: pick `custom` to open a two-step color builder — choose your primary color, then your slider/accent color, from a palette of named colors. The selection persists and applies to all cc output (rich console + prompt-toolkit selectors + log levels).

## Themes

| Name | Primary | Notes |
|---|---|---|
| `default` | cyan | The shipping default |
| `purple` | `#a78bfa` | Violet primary, yellow accents |
| `chronocoder` | `#FFCC00` | Yellow primary, maroon accents |
| `custom` | user-picked | Pick named colors for primary + slider |

## What it changes

The theme affects:

- All rich-console output (tables, panels, log levels)
- The prompt-toolkit selector colors (env picker, multi-select, autocomplete)
- The boxed status card in `cc stat`
- Color-coded values throughout the CLI (branch, database, env name, etc.)

The web `/settings` page has its own independent theme picker for the dashboard UI.

## Related

- [`cc config`](README.md) — change other settings interactively
- [`cc setup`](../setup.md) — first-time wizard (includes theme as a step)
