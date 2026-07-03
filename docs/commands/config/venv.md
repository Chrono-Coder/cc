# cc config venv

Interactive TUI for managing the pyenv virtualenv linked to an Odoo version.

## Usage

```bash
cc config venv            # manage the active version's virtualenv
cc config venv -v 19      # target a specific version
```

## Flags

| Flag | Description |
|------|-------------|
| `-v`, `--version` | Target a specific Odoo version by name instead of the active one (tab-completable) |

## Actions

When a virtualenv is already linked, the interactive menu offers:

| Action | Description |
|--------|-------------|
| Activate | Activate the virtualenv in the current shell |
| Reinstall | Reinstall Odoo requirements into the existing virtualenv |
| Reinit | Delete and recreate the virtualenv with a Python version picker, then reinstall requirements |
| Rename | Recreate under a new name, reinstall requirements, delete the old one, and relink |
| Unlink | Delete the virtualenv and remove its link from this version |
| Link | Link a different pyenv virtualenv (or create a new one) and relink this version |

When no virtualenv is linked yet, the only option is **Link a virtualenv** — choose an
existing pyenv virtualenv or create a fresh one (named `cc-<version>` by default) and
optionally install Odoo requirements into it.

Requires `pyenv` and `pyenv-virtualenv` to be installed and on `PATH`. Activate works
only with cc's shell integration in place (it writes `pyenv activate` to `CC_RUN_FILE`);
see [`cc config shell`](shell.md).

## Related

- [`cc config shell`](shell.md) — shell integration that makes Activate work
- [`cc setup`](../setup.md) — first-time wizard (includes linking a virtualenv as a step)
