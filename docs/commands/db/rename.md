# cc db rename

Rename a database — both the PostgreSQL database **and** cc's record.

## Usage

```bash
cc db rename <old> <new>
```

## Arguments

| Argument | Description |
|----------|-------------|
| `old` | Current database name (tab-completable) |
| `new` | New database name |

## What it does

1. Renames the PostgreSQL database (direct connection or via `docker exec`, so it works on a dockerized Postgres) and updates cc's cache record.
2. If the renamed database is the active environment's database, rewrites `cc.database` in the version's `settings.json` to the new name.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db use`](use.md) — set the active database
- [`cc db drop`](drop.md) — drop a database
