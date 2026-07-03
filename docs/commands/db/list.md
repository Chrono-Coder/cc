# cc db list

List the databases linked to the current environment, with the active one marked.

## Usage

```bash
cc db list
```

## What it does

- Requires an active environment — run [`cc switch`](../switch.md) first.
- Prints a table of the environment's pool (plus the active database if it isn't already in the pool). The active database is marked with a ●, and any database with a live `-CC-COPY` is marked with a ✓ in the Copy column.
- If nothing is linked, it points you at [`cc db use`](use.md).

This reads from the local metadata cache, so it's instant and never blocks on
`psql`.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db use`](use.md) — set the active database
- [`cc db link`](link.md) / [`cc db unlink`](unlink.md) — manage the pool
