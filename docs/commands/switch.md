# cc switch

Switch your active project and configure your IDE.

## Usage

```bash
cc switch [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project name (tab-completable). If omitted, opens a picker on your 5 most recently used environments (10 with `--all`). The cursor starts on the active env; **type to filter** across *all* environments, not just the ones shown. `cc switch -` jumps straight back to the previous env. |

## Flags

| Flag | Description |
|------|-------------|
| `-s`, `--silent` | Switch without opening the IDE |
| `-n`, `--new` | Open the project in a new IDE window (auto-enabled in VSCode terminals) |
| `-e`, `--env` | Switch directly to a named environment: `cc switch --env staging` |
| `-a`, `--all` | Include merged/archived environments in the picker |
| `--no-pull` | Skip fetch + rebase in R&D repos on switch |

<!-- 📸 IMAGE: GIF of a full cc switch — selector, branch checkout, IDE opening -->

## What It Does

1. Looks up the project in the database
2. If multiple environments exist, prompts you to choose one
3. Checks if you've been on the previous project longer than your flag threshold — shows a summary if so
4. Runs `~/.cc-cli/hooks/pre_switch` if it exists
5. Sets the environment as **the** active environment — the one you last switched to. (With [multi-version mode](../concepts/multi-version-mode.md) on, cc keeps one active env per Odoo version instead.)
6. Updates the editor's per-switch state (e.g. `.vscode/settings.json` — database, addons paths, modules, Python interpreter, ports) via registered IDE writers. `launch.json` is **not** touched on switch; debug templates picked up via `${config:cc.*}` variable indirection. Run `cc config ide setup` once to (re)write the templates.
7. Checks out the environment's git branch in the project repo. R&D workspaces check the branch out across every shared Odoo repo (odoo, enterprise, design-themes, upgrade, upgrade-util). If a checkout fails — usually uncommitted changes — the switch reports it instead of a false success and exits non-zero.
8. Changes directory to the project path
9. Opens the project in your IDE
10. Triggers a background `git fetch` for odoo/enterprise/design-themes if auto-fetch is enabled and the interval has elapsed (default 24h) — runs silently in the background, does not block the switch
11. Runs `~/.cc-cli/hooks/post_switch` if it exists

## Switch Hooks

You can run custom scripts before and after every switch by placing executables at:

```
~/.cc-cli/hooks/pre_switch
~/.cc-cli/hooks/post_switch
```

Any line printed to **stdout** is eval'd in the parent shell — this is how hooks can activate virtualenvs or export environment variables:

```bash
#!/bin/bash
# ~/.cc-cli/hooks/post_switch — activate a project-specific venv
if [ -f "$CC_PROJECT_PATH/.venv/bin/activate" ]; then
  echo "source $CC_PROJECT_PATH/.venv/bin/activate"
fi
```

### Environment Variables Available in Hooks

| Variable | Description |
|---|---|
| `CC_ENV_NAME` | Environment name (e.g. `acme_staging`) |
| `CC_PROJECT_NAME` | Project name (e.g. `acme`) |
| `CC_PROJECT_PATH` | Absolute path to the project directory |
| `CC_DATABASE` | Linked database name |
| `CC_BRANCH` | Configured branch name |
| `CC_VERSION` | Odoo version (e.g. `19.0`) |

Hooks have a 30-second timeout. Failures are logged as warnings but do not abort the switch.

## The picker

`cc switch` with no name (or `--env <name>` that matches more than one project) opens
a two-pane selector: env names on the left, the highlighted env's branch / database /
last-used / modules on the right. The cursor opens **on the active env**, so re-confirming
where you are is a single Enter.

| Key | Action |
|-----|--------|
| `↑` / `↓` | Move the cursor |
| `↵` | Select the highlighted env |
| `esc` / `Ctrl-C` | Cancel without switching |
| `Backspace` | Delete the last filter character |
| any printable char | Append to the filter (type-to-filter) |

**How the filter works.** Each character you type appends to a filter string and the
list narrows immediately. Matching is a **case-insensitive substring** test against the
**full** environment name (the `project_env` form, so typing part of the project name
works too). It searches the **entire** environment set — not just the rows currently on
screen. The cursor jumps back to the top of the filtered list on every keystroke, so the
first match is one Enter away; `Backspace` widens it again. The footer shows your position
(`n of total`) and echoes the active `/filter`.

The list is **windowed**: it shows about 10 rows at a time and scrolls to keep the cursor
centred. That cap is only the *view* — filtering and navigation always reach the whole set.
On a narrow terminal the right detail pane drops and the picker collapses to a single
column. The set it draws from is the recency/lifecycle-filtered list (see `--all` to
include merged/archived envs).

## Examples

```bash
cc switch acme                # switch to acme, open IDE
cc switch acme -s             # switch silently (no IDE open)
cc switch acme -n             # open in new window
cc switch -                   # jump back to the previous environment
cc switch                     # show recent envs picker
cc switch --env staging       # switch directly to "staging" environment
```
