# Command Reference

cc's CLI is **noun-grouped**: `cc <group> <verb>` (e.g. `cc db use`, `cc git pr`,
`cc project env list`). A handful of hot-path commands stay flat. Run `cc <group>`
with no verb to see that group's help, or `cc help <command>` for any command.

## Flat commands

| Command | Description |
|---------|-------------|
| [`cc switch`](switch.md) | Switch active project/environment, configure the IDE, open it |
| [`cc cd`](cd.md) | Change directory to the active environment |
| [`cc stat`](stat.md) | Show the active environment |
| [`cc setup`](setup.md) | First-time wizard — settings, versions, pyenv, shell, theme |
| [`cc workspace`](workspace.md) | Manage workspaces — groups of projects sharing an Odoo version |

## `cc run` — Odoo runtime

| Command | Description |
|---------|-------------|
| [`cc run server`](run.md#start-the-server) | Start Odoo for the active environment |
| [`cc run shell`](run.md#open-an-odoo-shell) | Open an interactive Odoo shell |

## `cc db` — Databases

| Command | Description |
|---------|-------------|
| [`cc db create`](db/create.md) | Restore a project dump or initialize and select a fresh Odoo database |
| [`cc db use`](db/use.md) | Set the active database for the current environment |
| [`cc db list`](db/list.md) | List databases linked to the current environment |
| [`cc db drop`](db/drop.md) | Drop a PostgreSQL database (local or dockerized) |
| [`cc db init`](db/init.md) | Create a database from a dump file |
| [`cc db copy`](db/copy.md) | Quick in-place database copy (`-CC-COPY` suffix) |
| [`cc db restore`](db/restore.md) | Restore from a CC copy |
| [`cc db backup`](db/backup.md) | Named DB snapshots — create, list, restore, delete |
| [`cc db rename`](db/rename.md) | Rename a database (CC record + PostgreSQL) |
| [`cc db link`](db/link.md) | Add a database to the current environment's pool |
| [`cc db unlink`](db/unlink.md) | Remove a database from the environment's pool |
| [`cc db extend`](db/extend.md) | Push the active DB's expiry to 2099, disable the update cron |
| [`cc db check`](db/check.md) | Diagnose the Postgres connection |

## `cc git` — Git & GitHub

| Command | Description |
|---------|-------------|
| [`cc git branch`](git/branch.md) | Change the branch of the active/chosen environment |
| [`cc git fetch`](git/fetch.md) | `git fetch` across all version repos |
| [`cc git pr`](git/pr.md) | PR lifecycle — list, create, view, merge, checkout, checks |
| [`cc git github`](git/github.md) | Open the GitHub repo in a browser |

## `cc config` — Configuration

Bare `cc config` opens the interactive settings picker; `-l`/`--list` prints all settings.

| Command | Description |
|---------|-------------|
| [`cc config`](config/README.md) | Settings picker (bare) / `--list` |
| [`cc config ide`](config/ide.md) | Manage editor integration writers (setup, list) |
| [`cc config venv`](config/venv.md) | Manage the pyenv virtualenv linked to the active version |
| [`cc config theme`](config/theme.md) | Pick or set the color theme |
| [`cc config shell`](config/shell.md) | Install / check shell integration (zsh, bash, fish) |
| [`cc config completion`](config/completion.md) | Print a native completion script |
| [`cc config reset`](config/reset.md) | Drop the CC SQLite schema (full reset) |

## `cc daemon` — Background daemon

| Command | Description |
|---------|-------------|
| [`cc daemon`](daemon/README.md) | Lifecycle — start, stop, restart, status |
| [`cc daemon logs`](daemon/logs.md) | Tail daemon log files; filter by source or level |

## `cc project` — Projects & environments

| Command | Description |
|---------|-------------|
| [`cc project create`](project/create.md) | Create a project |
| [`cc project list`](project/list.md) | List projects |
| [`cc project delete`](project/delete.md) | Delete a project and its environments |
| [`cc project keep`](project/keep.md) | Exempt a project from auto-archiving (toggle) |
| [`cc project env`](project/env.md) | Manage environments — create, list, delete, edit, archive, … |
| [`cc project cloc`](project/cloc.md) | Count lines of code; `-a` for active modules only |
| [`cc project module`](project/module.md) | Install/update modules; `-i`/`-u` sets launch mode |
| [`cc project open`](project/open.md) | Open the active environment in your IDE |

## Other

| Command | Description |
|---------|-------------|
| [`cc web`](web.md) | Start the CC companion web app |
| [`cc time`](time.md) | View timesheet; start/end manual entries, edit, review |
| [`cc intel`](intel.md) | Manage the skill telemetry index — scan, add-repo, list-repos |
| [`cc reindex`](reindex.md) | Walk new commits, run language packs, update skill tags |
| [`cc sync`](sync.md) | Synchronize local data with the CC server |
| [`cc sh`](sh.md) | Open the Odoo.sh project in the browser |
| [`cc psx`](psx.md) | Open PSX runbot tests in a browser |
| [`cc ticket`](ticket.md) | Open the linked ticket in a browser |
