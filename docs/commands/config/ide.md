# cc config ide

Manage IDE writer plugins — list registered writers and run one-time setup for the active workspace.

## Usage

```bash
cc config ide [action] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `action` | One of `list`, `setup`. Defaults to `list`. |

## Flags

| Flag | Description |
|------|-------------|
| `--path PATH` | Override the workspace path (defaults to the active version's `path`) |

## Actions

### `cc config ide list`

Shows every registered IDE writer (built-in + plugins) and which ones are active for the current workspace.

```bash
$ cc config ide list

Registered IDE writers
  vscode       ● active
  cursor       ○ inactive

workspace: /Users/jane/odoo/worktrees/17.0
```

A writer is **active** when:

- the `cc.ide` setting is `auto` (the default) AND the writer's `detect()` returns True for the workspace, OR
- the `cc.ide` setting explicitly names it (e.g. `cc.ide = vscode,cursor`)

### `cc config ide setup`

Writes one-time editor templates for the active version's path. This is the only legitimate path that touches files like `launch.json` (for VSCode). `cc switch` never edits them.

```bash
$ cc config ide setup

✓ vscode templates written → /Users/jane/odoo/worktrees/17.0
```

Run this:

- After installing cc, once per workspace
- After updating cc — to pick up new template entries in the latest version
- Manually any time you want to re-apply the templates

If `cc.ide` is set to `none` or no writer matches, this command exits with a warning.

## What gets written

### VSCode / Cursor

| File | When | What |
|------|------|------|
| `.vscode/launch.json` | `cc config ide setup` (and only then) | Debug configurations `CC: Odoo` and `CC: Odoo [test]`, merged with your existing entries |
| `.vscode/settings.json` | Every `cc switch` | `cc.odooBin`, `cc.port`, `cc.database`, `cc.addonsPath`, `cc.modules`, `cc.upgradePath`, `cc.initMode`, `python.defaultInterpreterPath` |

The launch.json entries reference settings.json keys via `${config:cc.X}` indirection — so on each switch, the debugger picks up the new database / addons / modules without launch.json itself ever changing.

## Examples

```bash
# Inspect what's registered + which writers will run on next switch
cc config ide list

# Write VSCode/Cursor templates for the active workspace
cc config ide setup

# Set up a different workspace explicitly
cc config ide setup --path ~/odoo/worktrees/18.0

# Disable IDE integration entirely, or force a writer
cc config           # set IDE → None / Cursor via the picker
```

## Plugin development

Writing your own writer for an editor cc doesn't ship out of the box — see [IDE Writers](../../concepts/ide-writers.md) for the interface, discovery mechanism, and a minimal example.

## Related

- [IDE Writers](../../concepts/ide-writers.md) — concept and plugin authoring
- [`cc switch`](../switch.md) — invokes `writer.apply()` on every switch
- [`cc workspace`](../workspace.md) — `cc workspace add` prompts to run `cc config ide setup` automatically
