# cc project open

Open a project in your IDE without switching the active environment.

## Usage

```bash
cc project open [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project to open. Omit to open the **active** environment. |

## Flags

| Flag | Description |
|------|-------------|
| `-n`, `--new` | Open in a new IDE window |

If the named project has multiple environments, cc prompts you to pick one. A name
that doesn't match an existing project offers to create it.

## Examples

```bash
cc project open             # open the active environment in your IDE
cc project open acme        # open 'acme' in the current IDE window
cc project open acme -n     # open 'acme' in a new window
```

## Difference from cc switch

`cc project open` opens the IDE for a project without changing your active
environment, branch, or editor config. Use it to browse a project's code without
switching context.

[`cc switch`](../switch.md) is a full context switch — it changes the active
environment, checks out the branch, and updates the editor's per-switch settings.

## Related

- [`cc switch`](../switch.md) — switch the active environment and open the IDE
- [`cc project env`](env.md) — manage environments
- [Command Reference](../README.md)
