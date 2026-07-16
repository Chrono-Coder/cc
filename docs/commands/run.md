# cc run

Launch Odoo directly from the environment selected with `cc switch`. CC uses the
registered Odoo version path, linked pyenv interpreter, active database, port,
project directory, and discovered addons paths.

## Start the server

```bash
cc run server
cc run server --database another_db
cc run server --no-dev
cc run server -- --log-level=debug
```

The server runs in the foreground so logs and `Ctrl+C` work normally. Development
mode (`--dev=all`) is enabled by default.

## Open an Odoo shell

```bash
cc run shell
cc run shell --database another_db
cc run shell -- --log-level=debug
```

The shell inherits the current terminal's input and output and connects to the
active database.

## Create or restore a database

Create a clean Odoo database and select it for the active environment (see
[`cc db create`](db/create.md)):

```bash
cc db create my_project
cc db create my_project --modules base,my_module
```

To restore an Odoo server dump instead, use the existing dump workflow:

```bash
cc db init my_project
```

`cc db init` searches the configured dump directory for a zip containing
`dump.sql`, restores its filestore when applicable, loads the database through
the configured native or Docker PostgreSQL backend, and selects it for the active
environment.
