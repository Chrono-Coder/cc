# cc db copy

Create a snapshot copy of a PostgreSQL database. The copy is stored as
`<db_name>-CC-COPY` and can be restored later with [`cc db restore`](restore.md).

## Usage

```bash
cc db copy <name>
cc db copy                  # detect the DB from the active environment
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to copy (tab-completable). If omitted, cc reads the active environment's linked database, falling back to `settings.json` / `launch.json` detection on the version path. |

## What it does

- Routed through the daemon (direct connection or `docker exec`) — `CREATE DATABASE … TEMPLATE`, dropping any stale copy first, so it works on a dockerized Postgres too.
- If a copy already exists, it is dropped and recreated.

## Examples

```bash
cc db copy my_project_v17
# → Copies my_project_v17 → my_project_v17-CC-COPY

cc db copy
# → Detects the DB from the active environment and copies it
```

## Related

- [`cc db`](README.md) — database group overview
- [`cc db restore`](restore.md) — restore the copy back to the original database
- [`cc db backup`](backup.md) — named, file-based snapshots (separate from `-CC-COPY`)
