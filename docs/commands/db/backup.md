# cc db backup

Create and manage named database snapshots for an environment. Snapshots are
stored as PostgreSQL custom-format dumps (`pg_dump -Fc`) and tracked in cc's
internal records with metadata.

Backups are stored at: `~/.cc-cli/backups/{env_name}/{timestamp}_{name}.dump`

## Usage

```bash
cc db backup create [env] [-n NAME] [--note NOTE]
cc db backup list   [env]
cc db backup restore [env]
cc db backup delete  [env]
```

If no environment is given, cc uses the active environment. If no action is given,
cc defaults to `list`.

## Arguments

| Argument | Description |
|----------|-------------|
| `action` | One of `create`, `list`, `restore`, `delete`. Defaults to `list`. |
| `env` | Environment name (tab-completable). Defaults to the active environment. |

## Actions

| Action | Description |
|--------|-------------|
| `create` | Dump the environment's database to a named snapshot |
| `list` | List all snapshots, grouped by database if no environment is given |
| `restore` | Pick a snapshot and restore it (drops and recreates the database) |
| `delete` | Pick a snapshot and permanently delete it |

## Flags

| Flag | Description |
|------|-------------|
| `-n NAME`, `--name NAME` | Name for the snapshot (create only). Auto-generated if omitted: `{env}-{YYYY-MM-DD-HHMM}` |
| `--note NOTE` | Optional note attached to the snapshot (create only) |

## Examples

```bash
cc db backup create
# → Dumps active env's DB, auto-names the snapshot

cc db backup create my-env -n before-migration --note "clean v17 before upgrade"
# → Named snapshot with a note

cc db backup list
# → Lists all snapshots across all environments, grouped by database

cc db backup list my-env
# → Lists snapshots for my-env only

cc db backup restore my-env
# → Interactive picker → confirm → dropdb + createdb + pg_restore

cc db backup delete my-env
# → Interactive picker → confirm → removes file and record
```

## Notes

- cc warns if an environment already has 5 or more snapshots when you run `create`.
- Restore always targets the **same database** the snapshot was taken from. To restore into a different database, use [`cc db use`](use.md) to relink first.
- Snapshots are independent of [`cc db copy`](copy.md) / [`cc db restore`](restore.md) (which use a `-CC-COPY` suffix instead).

## Related

- [`cc db`](README.md) — database group overview
- [`cc db use`](use.md) — change the active database
- [`cc db copy`](copy.md) — lightweight in-place database copy
- [`cc db restore`](restore.md) — restore from a CC copy
