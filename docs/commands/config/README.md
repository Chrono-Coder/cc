# cc config

Configure cc. Bare `cc config` opens an interactive single-setting picker; its verbs
handle dedicated concerns (IDE writers, virtualenvs, theme, shell integration,
completion, reset).

For the first-time walkthrough (settings + versions + pyenv + shell + theme), use
[`cc setup`](../setup.md).

## Usage

```bash
cc config              # interactive settings picker
cc config -l           # list current settings as a table
cc config <verb> …     # run a config verb (see table below)
```

## Flags

| Flag | Description |
|------|-------------|
| `-l`, `--list` | Print all settings + current values as a themed table |

## The picker

`cc config` with no args opens a picker showing every setting and its current value.
Arrow-pick one, get prompted for the new value (typed input, boolean toggle, enum
select, or directory path depending on the setting's type), and it's saved.

```
╭ Choose setting ──────────────────────────────────────╮
│ ❯ IDE                              cursor            │
│   Downloads path                   ~/Downloads       │
│   Multi-version mode               false             │
│   Timesheet flag threshold         60                │
│   Prompt on flagged switch         true              │
│   Auto-fetch                       false             │
│   Auto-fetch interval (h)          24                │
│   EOD auto-stop time                                 │
│   Color theme                      chronocoder       │
│   Discover workspaces                                │
╰──────────────────────────────────────────────────────╯
```

One change per invocation — run again to flip another setting. The final entry,
**Discover workspaces**, jumps into the version-discovery flow (the same step
[`cc setup`](../setup.md) runs).

## Verbs

| Verb | Description |
|------|-------------|
| [`cc config ide`](ide.md) | List IDE writers and run one-time editor setup |
| [`cc config venv`](venv.md) | Manage the pyenv virtualenv linked to an Odoo version |
| [`cc config theme`](theme.md) | Pick or set the cc color theme |
| [`cc config shell`](shell.md) | Install / check cc shell integration (zsh, bash, fish) |
| [`cc config completion`](completion.md) | Print a native shell completion script |
| [`cc config reset`](reset.md) | Delete cc's internal database (irreversible) |

## Settings

| Setting | Type | Description |
| --- | --- | --- |
| IDE | enum | `auto` (default), `code`, `cursor`, `none`, or comma-separated writer names. Drives both the launcher and the writer plugins on `cc switch`. See [IDE Writers](../../concepts/ide-writers.md). |
| Downloads path | path | Where `cc db init` looks for dump files (default: `~/Downloads`) |
| Multi-version mode | bool | Track a separate active env per Odoo version (off by default = a single active env). See [Multi-Version Mode](../../concepts/multi-version-mode.md). |
| Auto-fetch | bool | Background `git fetch` on switch, throttled by interval |
| Fetch interval (hours) | int | Minimum hours between background fetches per version (default 24) |
| Flag threshold (minutes) | int | Sessions longer than this get ⚑ flagged in `cc time` (default 60) |
| Prompt on flagged switch | bool | Confirm before switching away from a long session |
| EOD auto-stop time | str | `HH:MM` — auto-punch-out if you forget. Blank to disable. |
| Color theme | enum | One of `default`, `purple`, `chronocoder`, `custom` |

For an explanation of each setting's effect, see [Settings Guide](../../configuration/settings.md).

## Related

- [`cc setup`](../setup.md) — first-time wizard (or re-run to walk every step)
- [`cc config theme`](theme.md) — change theme without going through the picker
- [`cc config shell`](shell.md) — (re)install shell integration
- [Command Reference](../README.md) — every cc command
