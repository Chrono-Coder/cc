# cc db link

Add a database to the current environment's pool, without making it active.

## Usage

```bash
cc db link <name>
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to link (tab-completable) |

## What it does

- Requires an active environment — run [`cc switch`](../switch.md) first.
- Adds the database to the environment's pool. This does **not** change the active database (`cc.database` / what `launch.json` runs) — use [`cc db use`](use.md) to make a pool database active.

The pool lets you keep multiple databases associated with one environment (e.g.
clean, test, prod-copy) and switch between them easily.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db unlink`](unlink.md) — remove a database from the pool
- [`cc db use`](use.md) — make a pool database active
- [`cc db list`](list.md) — show the pool
