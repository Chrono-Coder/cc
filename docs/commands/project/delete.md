# cc project delete

Delete a project and all of its environments from cc's database.

## Usage

```bash
cc project delete [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project to delete. Omit to be prompted. |

## Flags

| Flag | Description |
|------|-------------|
| `-y`, `--yes` | Skip confirmation prompt |

## Examples

```bash
cc project delete acme       # delete 'acme' and all its environments
cc project delete acme -y    # skip the confirmation
```

## Notes

This is destructive — it removes the project record and all associated
environments and switch history from cc's database. Your actual code and
PostgreSQL databases are **not** affected.

## Related

- [`cc project create`](create.md) — create a project
- [`cc project env`](env.md) `delete` — delete a single environment
- [Command Reference](../README.md)
