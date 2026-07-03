# cc project create

Create a project. You rarely need this directly — [`cc switch <name>`](../switch.md)
creates a project on the fly if it doesn't exist.

## Usage

```bash
cc project create [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project name. Omit to be prompted for one. |

## Flags

| Flag | Description |
|------|-------------|
| `--virtual` | Create a virtual project (no local path, time tracking only) |
| `-w`, `--workspace` | Create the project in a workspace |
| `-y`, `--yes` | Skip confirmation prompt |

When you create a project inside an R&D workspace (`-w`, or auto-detected from the
current directory), cc discovers the ticket's forward-port chain and sets up the
matching environments. Otherwise it creates a single environment.

## Examples

```bash
cc project create acme              # create project 'acme'
cc project create acme -w rnd       # create 'acme' in the 'rnd' workspace
cc project create billing --virtual # time-tracking-only project, no code path
```

## Related

- [`cc project list`](list.md) — list projects
- [`cc project delete`](delete.md) — delete a project
- [`cc project env`](env.md) — add environments to a project
- [`cc switch`](../switch.md) — switch to (and auto-create) a project
- [Command Reference](../README.md)
