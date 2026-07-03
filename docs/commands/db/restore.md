# cc db restore

Restore a PostgreSQL database from its cc copy (`<db_name>-CC-COPY`). The original
database is dropped and recreated from the copy.

## Usage

```bash
cc db restore <name>
cc db restore              # detect the DB from the active environment
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Database to restore (tab-completable). If omitted, cc detects it from the version path's `settings.json` / `launch.json`. |

## What it does

- Routed through the daemon (direct connection or `docker exec`): it verifies the `<name>-CC-COPY` template exists in live Postgres **before** dropping the target, then `CREATE DATABASE … TEMPLATE` the copy. Works on a dockerized Postgres too.
- You must run [`cc db copy`](copy.md) first. If no copy exists, the command aborts before touching the target.

## Examples

```bash
cc db restore my_project_v17
# → Drops my_project_v17, restores from my_project_v17-CC-COPY

cc db restore
# → Detects the DB from the active environment and restores it
```

## Related

- [`cc db`](README.md) — database group overview
- [`cc db copy`](copy.md) — create the copy this restores from
- [`cc db backup`](backup.md) — named, file-based snapshots
