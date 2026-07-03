# cc setup

Interactive first-time configuration wizard. Walks the full sequence:

1. **Settings** — IDE, repo structure, multi-version mode, auto-fetch, timesheet, theme
2. **Odoo versions** — filesystem scan, prompt to register each discovered install
3. **pyenv** — for each registered version, link or create a virtualenv
4. **Shell integration** — install the `cc` shell function, daemon auto-start, prompt segment
5. **Theme** — pick a color palette (or build a custom one)

Runnable anytime — re-running on a configured machine pre-fills current values, shows "already registered" for known versions, skips shell install if it's already in place.

## Usage

```bash
cc setup
```

No arguments. Walk through each step interactively.

## Used during install

[`install.sh`](https://github.com/Chrono-Coder/cc/blob/main/install.sh) offers to run `cc setup` as the final step. You can run it manually any time later.

## What if I only want to change one thing?

Use the dedicated verb:

- Settings → [`cc config`](config/README.md) (single-setting picker)
- Theme → [`cc config theme`](config/theme.md)
- Shell integration → [`cc config shell install`](config/shell.md)
- Add an Odoo version / workspace → [`cc workspace add`](workspace.md)
- pyenv virtualenv → [`cc config venv`](config/venv.md)

## Related

- [Installation](../getting-started/installation.md)
- [Settings Guide](../configuration/settings.md)
- [`cc config`](config/README.md) — day-to-day single-setting tweaks
