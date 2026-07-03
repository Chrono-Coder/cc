# cc db unlink

Remove a database from the current environment's pool.

## Usage

```bash
cc db unlink <name>
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to unlink (tab-completable) |

## What it does

- Requires an active environment — run [`cc switch`](../switch.md) first.
- Removes the database from the environment's pool. This only touches cc's bookkeeping — it does **not** drop the database. Use [`cc db drop`](drop.md) to destroy the database itself.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db link`](link.md) — add a database to the pool
- [`cc db drop`](drop.md) — drop the database from PostgreSQL
- [`cc db list`](list.md) — show the pool
