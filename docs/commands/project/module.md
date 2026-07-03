# cc project module

Update the module list for your active environment. Your selection is saved to the
environment and written to `.vscode/settings.json` as `cc.modules` (and `cc.initMode`
for the launch mode), which `launch.json` picks up via `${config:cc.modules}` and
`${config:cc.initMode}`.

## Usage

```bash
cc project module [names...] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `names` | Module names to set. Omit for an interactive checkbox picker. |

## Flags

| Flag | Description |
|------|-------------|
| `-r`, `--replace` | Replace the full module list instead of adding to it |
| `-i`, `--install` | Set launch mode to install (`cc.initMode=-i`) |
| `-u`, `--update` | Set launch mode to update (`cc.initMode=-u`, default) |
| `-l`, `--list` | List the active modules for the current environment |

`-i`/`-u` may be combined with module names or the picker. Passed **alone** (no
names, no `--replace`), they just flip the launch mode for the already-active
modules. Omitting both leaves the current `cc.initMode` unchanged on an add.

## Examples

```bash
cc project module               # add modules, keep current launch mode
cc project module -l            # list active modules
cc project module -r            # replace the full module list (picker)
cc project module -i            # set launch mode to -i for the active modules
cc project module -u sale       # add 'sale', set launch mode to -u
cc project module -i purchase   # add 'purchase', set launch mode to -i
```

After saving, `launch.json` picks up the new module list and init mode
automatically — no manual edit needed.

## Related

- [`cc project cloc`](cloc.md) — count lines of code for the project's modules
- [`cc project env`](env.md) `edit` — edit an environment's modules interactively
- [`cc switch`](../switch.md) — writes the active modules into the editor config
- [Command Reference](../README.md)
