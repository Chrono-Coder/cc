# cc db init

Create a database from a zip dump file found in your configured download directory.

## Usage

```bash
cc db init                  # pick a dump from the download directory
cc db init <file_name>      # fuzzy-match a dump by name
cc db init -n my_db         # set the new database name
cc db init -p ~/dumps       # search a custom directory for dumps
```

## Arguments

| Argument | Description |
|----------|-------------|
| `file_name` | Dump to use. Fuzzy-matched against zips in the search directory; prompts if several match. Omit to pick from a list (newest first). |

## Flags

| Flag | Description |
|------|-------------|
| `-n`, `--name` | Name for the new database. If omitted, cc suggests one from the dump filename and lets you accept or edit it. |
| `-p`, `--path` | Directory to search for dumps. Defaults to the configured download path. |

## What it does

1. Looks in the search directory (`--path`, else the configured download path) for `.zip` dump files. Only zips containing a `dump.sql` are considered valid.
2. Selects the dump — by fuzzy name match, or from a newest-first picker.
3. Prompts for the target database name (suggested from `--name` or the filename).
4. Extracts the zip, then drops + recreates the database and loads `dump.sql` through the daemon — directly or via `docker exec -i psql` for a dockerized Postgres.
5. Runs the cleanup SQL afterwards (neutralizes mail servers, crons, etc.).
6. Copies the dump's `filestore/` to `~/.local/share/Odoo/filestore/<db_name>` for a native Odoo. For a dockerized Postgres the host filestore copy is skipped (its filestore lives in the container/volume).

## Configure the download directory

```bash
cc config
```

Pick the download path from the settings picker and set it to the folder where you
save dump files (e.g. `~/Downloads`). Or pass `--path` per invocation.

## Dump format

cc expects the standard Odoo backup zip:

```
backup.zip
  ├── dump.sql
  └── filestore/   (optional)
```

## Related

- [`cc db`](README.md) — database group overview
- [`cc db use`](use.md) — make the new database active
- [`cc db backup`](backup.md) — named snapshots (separate from dumps)
- [`cc config`](../config/README.md) — set the download path
