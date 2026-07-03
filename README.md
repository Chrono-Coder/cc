# cc

**A workflow tool for Odoo developers.**

Switching between Odoo projects means juggling branches, databases, addons paths, modules, Python environments, and editor configs — usually by hand, every time. `cc` does it in one command. It tracks your projects, environments, databases, and modules in a local SQLite database, exposes them over a daemon, and projects the right state into your editor whenever you switch.

```bash
cc switch acme       # one command:
                     # → check out acme's branch
                     # → set the database, modules, addons paths
                     # → activate the pyenv venv
                     # → update VSCode / Cursor settings so F5 runs the right thing
                     # → start your timesheet
                     # → open the project
```

Built by Odoo developers, for Odoo developers.

---

## Install

Requires Python ≥ 3.10 and Git.

```bash
git clone https://github.com/Chrono-Coder/cc.git && cd cc
./install.sh        # base install
./install.sh --sync # with the multi-device sync plugin
```

cc installs into its own venv at `~/.cc-cli/venv` and drops a shim into your `$PATH`. No system-Python pollution, no `--break-system-packages`. Works on macOS and Linux, zsh / bash / fish.

After install, run the setup wizard:

```bash
cc setup
```

It auto-detects your Odoo installations, your Python interpreters, and your editor of choice.

---

## What you get

### Project + environment switching

```bash
cc switch acme            # interactive picker if multiple envs exist
cc switch                 # show recent envs and pick one
cc stat                   # what's active right now
```

Each switch checks out the right git branch and updates the editor's `settings.json` (database, modules, addons paths, Python interpreter, ports) so debuggers and run configs pick up the right values. Editor templates (`launch.json` for VSCode) are written once via `cc config ide setup` and never touched again, so your customizations survive every switch.

### Database management

```bash
cc db use                 # pick a database for the active env
cc db copy                # snapshot the active db as <db>-CC-COPY
cc db restore             # roll the active db back to its -CC-COPY
cc db backup create       # named backup
cc db backup restore      # restore from a named backup
cc db init                # restore from a downloaded .zip dump
```

### Git + GitHub

```bash
cc git pr                 # list your open PRs, or create one for the current branch
cc git github             # open the project's GitHub
cc git fetch              # update all tracked Odoo versions
```

### Odoo SH

```bash
cc sh                     # open the Odoo SH page for the current project
```

### Tickets

```bash
cc ticket                 # open the ticket linked to the current branch
```

### Multi-device sync (experimental)

```bash
cc sync push              # push state to your central server
cc sync pull              # pull state on another machine
```

Background auto-sync every 5 minutes when configured. Install with `./install.sh --sync` (or `pip install -e ".[sync]"` from the repo). **Experimental:** the sync server is designed for a private, trusted network (e.g. a home LAN or VPN) — do not expose it to the internet.

### Web companion

```bash
cc web
```

Local Next.js dashboard at `http://localhost:3000` — active envs, GitHub PRs, timesheet charts, skill telemetry, health checks, log viewer, settings.

### Skill telemetry

```bash
cc intel scan             # index a git repo for skill tracking
cc reindex                # walk new commits, update skill tags
```

Indexes your commit history into a skill graph (which models you touch, which domains you work in, how often). The web companion's `/skills` page visualizes it.

---

## Architecture

```text
CLI · Web companion · Editor extensions
        ↓ JSON-RPC 2.0 (Unix socket)
      cc daemon  (~/.cc-cli/cc.sock)
        ↓
      Service layer  (src/cc/services/)
        ↓
      SQLite  (~/.cc-cli/cc_cli.db)
```

**CQRS-lite:** writes go through the daemon (one writer, no SQLite contention); reads hit the file directly through the same WAL-mode database.

See [Internals](https://cc.chronocoder.com/docs/internals) for the full architecture.

---

## Editor integration

cc ships with built-in writers for **VSCode** and **Cursor**. They share the same `.vscode/` format, so both editors get:

- Debugger templates in `launch.json` (`CC: Odoo`, `CC: Odoo [test]`)
- Per-switch `cc.*` keys in `settings.json` (database, addons paths, modules, ports, upgrade-util path, Python interpreter)

```bash
cc config ide setup       # write debugger templates (once per workspace)
cc config ide list        # show registered writers and which are active
```

### Other editors

cc's IDE integration is a plugin point — anyone can write a writer for PyCharm, vim, Zed, or whatever else. Implement `IdeWriter` (four methods: `name`, `detect`, `setup`, `apply`) and either ship it as a Python package with the `cc.ide_writers` entry point, or drop the file into `~/.cc-cli/ide_writers/`. See [`src/cc/ide/vscode.py`](src/cc/ide/vscode.py) for the reference implementation.

---

## Documentation

Full docs are at **[cc.chronocoder.com](https://cc.chronocoder.com)**.

- [Getting started](https://cc.chronocoder.com/docs/getting-started)
- [First switch](https://cc.chronocoder.com/docs/getting-started/first-switch)
- [Command reference](https://cc.chronocoder.com/docs/commands)
- [Configuration](https://cc.chronocoder.com/docs/configuration)
- [Concepts](https://cc.chronocoder.com/docs/concepts)
- [Internals / architecture](https://cc.chronocoder.com/docs/internals)
- [Changelog](https://cc.chronocoder.com/docs/changelog)

---

## Contributing

Contributions welcome. Open a pull request against `main` or start a discussion in [issues](https://github.com/Chrono-Coder/cc/issues). The test suite is `pytest tests/` from the repo root and runs against a temporary SQLite file per test, so it never touches your real cc database.

---

## License

[AGPL-3.0-only](LICENSE). If you fork cc and run it as a network service, your modifications must be made available to your users under the same license.

---

**Authors:** Peter-John Hein and Yousef Al Nashef.
