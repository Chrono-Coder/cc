# cc db drop

Drop one or more PostgreSQL databases. Works against a local Postgres **or** a
dockerized one whose port isn't published (cc reaches it via `docker exec`), and
keeps cc's metadata cache in sync.

## Usage

```bash
cc db drop <name>
cc db drop <name> -y
cc db drop                  # no name → multiselect from cached databases
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to drop (tab-completable). Omit to pick several from a checkbox list. |

## Flags

| Flag | Description |
|------|-------------|
| `-y`, `--yes` | Skip the confirmation prompt |

## What it does

1. With a `name`, drops that single database. With no `name`, shows a checkbox list of cached databases and drops everything you select.
2. Drops each database in Postgres — via a direct connection if reachable, otherwise via `docker exec` (no password needed; uses the container's local trust auth).
3. Flags the cache row `in_pg = false` (the row is kept, consistent with the background reconcile, so referential integrity and history survive). It stops being offered by completion.

It always confirms first (real data, irreversible) unless `-y` is given. With a
multiselect it confirms once for the whole batch.

## Safety

Dropping a database is the **only** way cc destroys real Postgres data, and it's
always explicit. Removing a cc *environment* or *project* never drops a database
— that only touches cc's bookkeeping.

## Related

- [`cc db`](README.md) — database group overview
- [`cc db check`](check.md) — diagnose the Postgres connection
- [`cc db copy`](copy.md) / [`cc db restore`](restore.md) — create databases
- [`cc project env`](../project/env.md) — manage environments
