# Installation

## Requirements

- Python 3.10+
- Git
- PostgreSQL (local)
- VS Code or Cursor (optional — for IDE integration)

## Install

```bash
git clone https://github.com/Chrono-Coder/cc.git ~/cc
cd ~/cc
./install.sh
```

The installer will:
1. Find Python 3.10+ on your system
2. Create an isolated venv at `~/.cc-cli/venv` (no system Python pollution)
3. Install cc-cli into the venv
4. Add `~/.cc-cli/bin` to your PATH
5. Install shell integration (zsh, bash, or fish)
6. Optionally run `cc setup` for first-time configuration

No pyenv required. No `pip install` into your system Python. cc lives entirely in its own venv and doesn't interfere with anything else.

### With sync plugin

```bash
./install.sh --sync
```

This adds encrypted multi-device sync support. See the [v3.3.0 changelog](../changelog.md#v330--may-2026) for details.

### Upgrading from an older cc version

The installer handles upgrades automatically:
- Detects and removes old pip installs
- Cleans stale entries from your shell rc file
- Regenerates shell integration with correct paths
- Your database and settings at `~/.cc-cli/` are preserved

## Verify

Restart your terminal (or `source ~/.zshrc`), then:

```bash
cc
```

You should see the cc welcome screen with getting started instructions.

## Optional: pyenv

cc integrates with [pyenv](https://github.com/pyenv/pyenv) to automatically activate the correct Python version when switching projects.

If pyenv is installed, cc will prompt you to link each Odoo version to a pyenv virtualenv during `cc setup`. On every `cc switch`, the terminal and VS Code interpreter will be updated automatically.

If pyenv is not installed, cc works fine — Python environment switching is simply skipped.

## First Run

Run the configuration wizard:

```bash
cc setup
```

This walks you through:
- Where your Odoo installations are (auto-discovers versions and git branches)
- IDE preference, dump file directory, repo structure
- Timesheet and auto-fetch settings
- Shell integration and theme

You only need to do this once. The installer offers to run it for you at the end. Safe to re-run anytime — it pre-fills current values and skips steps already done.

For daily tweaks:

- `cc config` — change a single setting
- `cc config theme` — change the color theme
- `cc workspace add` — register an additional Odoo version
- `cc shell install` — reinstall shell integration after a dotfile reset

---

Next: [Your First Switch](first-switch.md)
