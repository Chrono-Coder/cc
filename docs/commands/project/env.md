# cc project env

Manage the environments of a project. The first positional is an **action**; the
second is a target (a project for `list`/`create`, an environment name for
`delete`/`edit`/`archive`/…).

## Usage

```bash
cc project env [action] [target] [flags]
```

## Actions

| Action | Description |
|--------|-------------|
| `list` (default) | List environments for the active project (or `[target]` project) |
| `create` | Create an environment (no project given → project picker) |
| `delete` | Delete an environment (by name; collision → project picker) |
| `edit` | Edit an existing environment |
| `archive` | Set the environment's status to `archived` |
| `activate` | Set the environment's status to `active` |
| `merged` | Set the environment's status to `merged` |
| `pin` | Pin an environment so it always shows in the picker |
| `unpin` | Unpin an environment |

The old `add`/`remove` verbs still work as **silent aliases** for `create`/`delete`.

## Flags

| Flag | Description |
|------|-------------|
| `-y`, `--yes` | Skip confirmation prompt |
| `--json` | Output as JSON (`list` action only) |
| `--fw`, `--ports` | With `create`: scan the fork and add the ticket's forward-port environments |

Environment names aren't unique across projects. `delete`/`edit`/`archive`/`pin`
resolve by environment name; if the same name exists in more than one project, cc
pops a `project/env` picker instead of guessing. With no target, it acts on the
active project's environments.

## Examples

```bash
cc project env                      # list environments for the active project
cc project env list acme            # list environments for 'acme'
cc project env list --json          # machine-readable listing
cc project env create               # pick a project, then name the new environment
cc project env create acme          # create an environment in 'acme'
cc project env create acme --fw     # add the ticket's forward-port envs
cc project env delete staging       # delete the env named 'staging' (picker if ambiguous)
cc project env edit                 # interactive picker to edit an environment
cc project env archive old_feature  # mark an environment archived
cc project env pin staging          # keep 'staging' in the picker regardless of recency
```

## Edit options

When editing an environment, you can update:

- **Name** — rename the environment
- **Branch**, **Version**, **Project path**, **GitHub URL**
- **Database** — change the linked PostgreSQL database
- **Modules** — update the module list (used for `-u` in launch config)
- **Tickets** — the Odoo task IDs `cc ticket` opens (comma-separated)
- **Notes**, **Status** (active / merged / archived), **SSH Tunnel**

## Related

- [`cc switch`](../switch.md) — switch the active environment
- [`cc project module`](module.md) — change an environment's module list
- [`cc db`](../db/README.md) — manage an environment's databases
- [Projects & Environments](../../concepts/projects-environments.md)
- [Command Reference](../README.md)
