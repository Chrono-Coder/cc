# cc db create

Create an Odoo database for the active environment, either from a downloaded
server dump or through fresh initialization, then select it for that environment.

```bash
cc db create my_project
cc db create my_project --fresh
cc db create my_project --dump ~/Downloads/my_project.zip
cc db create my_project --modules base,my_module
cc db create my_project --no-module-picker
cc db create my_project --with-demo
```

The first picker scans the dump directory configured in `cc config`. Valid Odoo
zip dumps containing `dump.sql` are shown with filenames matching the active
project first, followed by the remaining dumps. Choose a dump to restore its
database and filestore, or choose **Fresh database** to continue with a clean DB.

For fresh databases, CC discovers modules in the active project (including its configured
internal-addons directory), opens a terminal picker, and lets you assign each
selected module one of three actions:

- **Install** — passed to Odoo with `-i`.
- **Upgrade** — passed to Odoo with `-u`.
- **Draft** — remembered for the environment but not run.

CC always installs `base`, disables demo data, and stops Odoo after initialization.
Use `--modules` for a non-interactive comma-separated install list, or
`--no-module-picker` to initialize only `base`. Use `--fresh` or `--dump PATH`
to bypass the source picker.

To initialize from an Odoo server dump instead, use [`cc db init`](init.md).
