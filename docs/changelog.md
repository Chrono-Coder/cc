# Changelog

## v4.0.1

- **`cc switch` project discovery no longer descends into cache directories.** Matching a project by name (e.g. `cc switch prompt`) surfaced junk paths like `.mypy_cache/3.10/prompt_toolkit` alongside the real project. Discovery now skips dotdirs (scoped to project lookup, so the `launch.json` search can still reach `.vscode/`) and bans the non-hidden vendor/cache dirs (`__pycache__`, `node_modules`, `venv`, `site-packages`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.tox`, `.cache`).

## v4.0.0 — first public release

cc goes public. 4.0 is the consolidation of the internal 3.1 → 3.11 line into one release: everything below this entry describes how it was built, but if you're arriving fresh, this is the version you install.

What you get:

- **One-command switching** — `cc switch <project>` checks out the branch, sets the database, modules and addons paths, activates the right Python env, updates your editor's settings, starts your timesheet, and opens the project.
- **A real database subsystem** — `cc db` use/copy/restore/backup/init/rename/extend against native or dockerized Postgres, with named snapshots and zip-dump restore.
- **Daemon architecture** — a Unix-socket JSON-RPC daemon serialises all writes (CLI, web, editor extensions); reads go straight to SQLite. Event buses on both sides keep features decoupled.
- **Web companion** — `cc web`: dashboard, projects, env detail with CI checks, timesheet charts, switch history, health checks, log viewer, settings. Local-token auth, localhost-bound by default.
- **Timesheet** — automatic on switch, manual `cc time start/end` spans with notes, editing, EOD auto-stop, CSV/JSON export.
- **Skill telemetry (intel)** — index your commit history into a searchable skill graph; `/skills` page, CV/appraisal export.
- **R&D workspaces (rnd)** — git-worktree workspaces over shared Odoo repos with switch-rebase and forward-port discovery.
- **Multi-device sync (experimental)** — push/pull state through a central server on a trusted network.
- Native shell integration for zsh/bash/fish: prompt segment, daemon auto-start, and tab completion generated from the CLI itself.

The internal 3.x sections below are preserved as development history.

## v3.11.0 — internal (rolled into 4.0)

Plugins folded back into core. The 3.10 split is reversed: `intel`, `rnd`, and the web companion are built into `cc` again, the plugin machinery is gone, and there is nothing extra to install. Everything ships in the one `cc` package; each feature is now turned on or off by a setting instead of by installing or uninstalling a plugin.

### What changed

- **`cc install`, `cc uninstall`, and `cc plugins` are removed.** So are the entry-point groups, the `plugins.repo` setting, and the standalone `cc-intel` / `cc-rnd` / `cc-web` packages. The `plugins/` folder is gone.
- **The extracted features move back into `src/cc/`.** `cc intel` / `cc reindex` (plus the `intel` RPC, its models, and the reindex-on-switch handler), the R&D workflow (`cc rnd …`), and `cc web` all live in core again. The Next.js companion moves to the repo-root `web/` directory and `cc web` builds and runs it in place.

### Toggle features with settings

Features are gated by config, not by what's installed — run `cc config` to switch them on or off. For example `intel.auto_reindex` (reindex on switch), `rnd.auto_rebase` (switch-rebase for R&D workspaces), and `timesheet.mode`. A feature you don't use simply stays disabled rather than uninstalled.

- **`rnd.auto_rebase`** (default on) controls whether `cc switch` in an R&D workspace checks out + rebases the env's branch across the shared Odoo repos. Off to switch without cc touching git. See [settings](configuration/settings.md).

### Timesheet — explicit spans

The timesheet gains a manual layer on top of the automatic switch-driven baseline. See [Timesheet](concepts/timesheet.md) and [`cc time`](commands/time.md).

- **Manual entries with notes.** `cc time start [env] --note <text>` opens an explicit span on an env (defaults to the active one); `cc time end --note <text>` closes it. An open entry runs until you end it.
- **Editing.** `cc time edit` / `cc time delete` / `cc time review` interactively adjust an entry's start, end, or note, or delete it. Editing an **auto** entry promotes it to authoritative.
- **Human-touched wins.** The day/week view resolves auto and manual entries together — authoritative spans (manual or edited) are kept whole, the auto baseline fills the gaps, and overlaps never double-count. `--csv` / `--json` emit the same resolved segments with source + note.
- **`timesheet.mode`.** New setting: `auto` (default — log a span on every switch) or `manual` (switches log nothing; only `cc time start/end` count).

### Multi-active environments return (opt-in)

The per-version active environment is back, behind a setting. With `multi_version_mode` **off** (the default) cc keeps a single active env — the one you last switched to, as in 3.8. Turn it **on** and cc keeps one active env per Odoo version, resolved from the current directory's version, so v17 and v18 stay independently active in parallel terminals. See [Multi-Version Mode](concepts/multi-version-mode.md).

### Projects

- **`cc project keep <name>`** toggles an exemption that keeps a project's environments out of the auto-archive sweep (`env.auto_stale_days`) — protect a long-running client or a project you check in on infrequently. Run it again to lift the exemption. See [`cc project keep`](commands/project/keep.md).

### Public-release hardening

A security and portability pass across every surface, ahead of the public release.

- **Web companion auth.** The companion now requires a local token: `cc web` generates it once (`~/.cc-cli/web.token`), opens the browser with it, and the app exchanges it for a session cookie. Non-local `Host` headers and cross-origin mutations are rejected, and `next dev` binds `127.0.0.1`. Deliberate LAN deployments opt out with `CC_WEB_ALLOW_REMOTE=1` (see `deploy/cc-web.service`).
- **Sync server hardening.** Only `sync.push` / `sync.pull` are network-callable (device enrollment is local-only), pushed rows are validated against the local schema, credential-shaped settings never sync in either direction, and the server is threaded with request timeouts and a payload cap. Sync remains experimental: run it on a trusted network only.
- **Portability.** Record creation no longer requires SQLite ≥ 3.35 (works on older LTS distros).
- **Configurable conventions.** The internal-addons directory, fuzzy-match clean words, and the `cc ticket` / `cc psx` URL templates are now settings (`odoo.internal_addons_dir`, `search.clean_words`, `ticket.url_template`, `psx.url_template`) instead of hardcoded company conventions.
- **Script safety.** Shell instructions written for the parent shell are properly quoted (paths with spaces or metacharacters), non-interactive runs fail instead of auto-picking the first option in selection prompts, `Ctrl+C` exits 130, and unhandled errors log a full traceback to `~/.cc-cli/logs/cc.log`.
- **Installer.** `install.sh` installs shell integration with the correct post-3.9 command and fish gets a native `fish_add_path` PATH entry; the setup wizard defaults shell integration to Yes.

## v3.10.0 — internal (rolled into 4.0)

The plugin system. Company-specific features leave the core and ship as installable plugins, so the public `cc` is a lean, generic Odoo-dev tool. Three very different features were extracted to prove it — and core runs identically whether or not any plugin is installed.

### Plugins

An installed package extends cc through **entry-point groups**, each loaded with per-entry isolation (a broken plugin warns, never breaks core):

- `cc.commands` — contribute commands / command groups.
- `cc.rpc_services` — add daemon RPC namespaces (never shadow a core one).
- `cc.models` — add ORM models; their tables are built on startup.
- `cc.settings` — add entries to the `cc config` registry.
- `cc.event_handlers` — react to CLI events (the 3.9 bus); `bus.collect()` adds a *gathering* hook that aggregates handler return values.
- `cc.daemon_handlers` — react to daemon-side events (the daemon bus now fans out to in-process handlers as well as the web SSE stream).

Core tolerates any plugin being absent: an index migration on a missing table is skipped (re-runs once the plugin installs), `sync` only touches tables that exist, and the web `/skills` page degrades to an empty state.

### Manage plugins

- **`cc plugins`** — list installed plugins and what each contributes.
- **`cc install <name>`** / **`cc uninstall <name>`** — add/remove a plugin in cc's own environment (auto-detects pip vs pipx). First-party short names (`intel`, `rnd`, `web`) resolve against the cc repo via the `plugins.repo` setting; any other name is a literal pip spec / git URL.

### First extractions (monorepo `plugins/`)

- **cc-intel** ← `intel` + `reindex` (commands, the `intel` RPC, the Repository/SkillTag/KnowledgeIndex models, and the post-switch reindex — now a daemon-side handler).
- **cc-rnd** ← the R&D workflow: `cc rnd create`/`consolidate` (git-worktree workspaces), `cc rnd project`/`fw` (forward-port discovery), and the switch-rebase (a `switch.checkout` collecting hook). The three R&D fields stay dormant on core models.
- **cc-web** ← `cc web` + the Next.js companion app.

## v3.9.0 — internal (rolled into 4.0)

Consolidation: a flatter CLI surface, plus the groundwork (an event bus) for an eventual plugin system.

### Noun-grouped commands

The CLI moves from ~39 flat commands to **`cc <group> <verb>`**. Nothing was public yet, so there are **no backwards-compat aliases** — the old flat names are gone.

- **`cc db`** — `use · list · drop · init · copy · restore · backup · rename · link · unlink · extend · check`. The old flag-overloaded `cc db` and the separate `cc dropdb` / `cc initdb` / `cc copy` / `cc restore` / `cc backup` are folded in. `cc db drop` with no name opens a **multiselect** to drop several databases at once.
- **`cc git`** — `branch · fetch · github · pr`.
- **`cc config`** — bare `cc config` still opens the settings picker; `ide · venv · theme · shell · completion · reset` nest under it.
- **`cc daemon`** — `start · stop · restart · status · logs` (the old `cc logs` is now `cc daemon logs`).
- **`cc project`** — `create · list · delete · env <verb> · cloc · module · open`. `cc switch` / `cc cd` / `cc stat` stay top-level.

### Under the hood

- **Event bus** (`cc.events`). Core commands no longer hard-call features: `cc switch` emits `switch.before`, and the timesheet punch-out is now a handler subscribed to it. Handlers run in-process (can prompt), are isolated from one another, and may cancel the command. This is the seam company-specific features (R&D, timesheet, web) will extract along.
- **Path prompts complete `$VAR` paths.** `$HOME/…` and other env-var paths now Tab-complete (previously only `~`, absolute, and CWD-relative did).

## v3.8.1 — June 23, 2026

Database hotfix (also carried by 3.9/3.10, which branch from it).

- **`cc db init` no longer fails on a live connection or times out mid-restore.** `init`/`copy`/`restore` now terminate active backends on the target before `DROP DATABASE` (a shared, backend-routed helper), so an open session can't block the drop with "database is being accessed by other users". And `cc db init` gives its daemon call a 30-min timeout — a full Odoo dump streams for minutes, far past the 10s default, so the client no longer bails while the restore is still running.

## v3.8.0 — June 14, 2026

Audit-driven improvements and refactors. Two architectural simplifications anchor the release:

- **Single active environment.** Dropped multi-active (per-version active slots) — active == focused == the env you last switched to == the one time tracks. `cc switch` moves one pointer and closes the prior time span. Multi-*version* support is unchanged. The `AppState` singleton now holds exactly one current env; stale per-version slots are gone, and `cc status` / the dashboard read the same single pointer.
- **Removed single-repo mode.** Multi-dir is the only layout (git worktrees cover the rest); the `repo_type` setting and its setup step are gone, along with `register_versions_single_repo`.

### Git safety + honest exit codes

- **Switch reports checkout failures instead of faking success.** When a branch checkout fails (usually uncommitted changes), `cc switch` says so and **exits non-zero** rather than printing a green checkmark. R&D switches track per-repo checkout failures across all shared repos.
- **Commands that fail now exit 1.** `Command.run()` maps a `False` return to `sys.exit(1)`, so `cc ... && next` chains and CI scripts behave.
- **R&D-aware, parallel fetch.** `cc fetch` understands R&D workspaces (fetches each shared repo) and fetches a version's repos **in parallel** (`ThreadPoolExecutor`) instead of serially.
- **Warnings go to stderr.** Logger routes `WARNING`+ to a stderr `Console` so stdout stays clean for piping/eval.

### Startup correctness

- **Daemon liveness is checked, not assumed.** The client probes that the socket is actually accepting connections (`_socket_is_live`) before reusing it, and waits for a live socket when it auto-starts the daemon — fixing races where a stale socket file looked "up".
- **`cc daemon status -q` / `--quiet`.** Silent status that exits 0 when running / 1 when not — the contract the shell integration uses to decide whether to auto-launch (`cc daemon status -q || cc daemon start`). See [daemon](commands/daemon/README.md).
- **Shell integration fixes.** The prompt segment now reads the single-active env directly; `bash` integration writes to `~/.bashrc` (not the wrong rc); `bash`/`fish` get a `__cc_env_segment`.

### Friendlier errors

- **Hidden `cc tunnel`.** Nobody used it — it's no longer registered with the CLI (absent from `cc help` and completion), though the file stays on disk and works if re-imported. See [tunnel](commands/tunnel.md).
- **PostgreSQL errors are translated.** `pg` service maps `OperationalError` (e.g. Postgres not running) to a readable `CCError` instead of a stack trace.

### Core switch loop

- **Deterministic ordering everywhere.** Added an `_order` class default to the ORM (`BaseEntity`); display models sort by `name ASC` (backups by `created_at DESC`) so lists, pickers, and JSON come back in a stable order regardless of insert order.
- **`cc switch -`** jumps straight back to the previous environment.
- **Cursor opens on the active env** in the picker — re-confirming where you are is a single Enter.
- **Type-to-filter picker.** The env selector filters as you type (case-insensitive substring across the *full* env set, not just the visible rows), with a scrolling window, a `n of total` footer, and status/pin badges. See the [picker section in switch](commands/switch.md#the-picker).
- **Real `cc help`** and per-command descriptions in `cc -h`.
- **Removed `cc switch -i`** (the init-mode flag) — init vs update is driven by the env's module set, not a switch flag.

### Verb consistency + collision UX

- **`cc env create|delete` and `cc project create|delete`** are the canonical verbs (cc *owns* these objects). The old `add`/`remove` keep working as **silent aliases** so habits and scripts don't break. Completion offers only the new verbs.
- **Env-name collision handling.** Env names aren't unique across projects, so `delete`/`edit`/`archive`/`--env`/`cc cd <name>` resolve by env name first and pop a `project/env` picker when the name is ambiguous, rather than guessing.
- **`cc env pin|unpin`** keeps an env in the picker regardless of recency.
- **`cc open` with no argument** opens the active env.
- **`cc env edit` gains a Tickets field** — the Odoo task IDs `cc ticket` opens.

### Git ship (PR + ticket)

- **`cc pr` number resolution falls back to branch.** When you don't pass a number, cc looks up the PR for the current branch (`gh pr list --head`).
- **`cc pr create` bases the PR on the active version's branch.**
- **`cc pr merge`** wired through the picker (open / checkout / merge keys).
- **`cc ticket`** prefers the env's `ticket_ids`, falling back to branch parsing.

### Timesheet

- **Local-day bucketing.** Days bucket by your local calendar day; the daily total sums actual worked spans and excludes time after a punch-out.
- **`cc time --week`** (per-day totals for the last 7 days) and **`cc time --csv`** export.
- **`cc time review`** to interactively fix or delete a mis-tracked entry; **`cc time --stop`** punches out gracefully (no error when already stopped).
- **Retention.** New `timesheet_retention_days` setting prunes old switch-log rows. See [settings](configuration/settings.md).

### Path prompts

- **Every path prompt gets Tab-completion, `~`/`$VAR` expansion, and existence validation** (`prompt_input_path`): filesystem completion, retry-on-missing, and a `dir`/`file`/`any` kind. Applied across `cc setup`, `cc workspace`, env project-path, and the (hidden) tunnel key prompt. See [prompts](commands/workspace.md).

### Databases — fast cache + works with dockerized PG

- **Self-discovering Postgres connector.** Instead of relying on libpq's compiled-in default (which broke reads on macOS, where the bundled libpq's socket dir didn't match the local server), cc probes a configured DSN → libpq default → common socket dirs → localhost TCP and uses the first that works. **`cc db check`** prints the probe so you can see how cc connects (or why it can't); set `pg.connection` for anything exotic.
- **Dockerized Postgres support.** The common Odoo-dev setup runs PG in a container with an unpublished port — unreachable by socket or TCP. cc reaches it via `docker exec psql` (no password; container-local trust), auto-discovering the container. This is what makes the DB features work on a typical Mac.
- **Postgres metadata cache.** A background daemon job (`database.reconcile`, every 120s) mirrors PG into the `Database` table (name, size, last login, is-Odoo, in-pg). Every reader — `cc db -l`, the companion's `/databases`, tab-completion — now hits SQLite and never blocks on `psql` (was ~500ms/read).
- **Lifecycle that works on docker.** New **`cc dropdb`** (and `cc db --remove`/`--rename`) route through the daemon — direct connection or `docker exec` — instead of raw `dropdb`/`psql` subprocess. **`cc env remove`** offers to drop the linked DB as a separate, clearly-marked prompt (default no, skips shared DBs, never under `-y`). Removing a cc env/project never destroys DB data — the cache is a mirror owned by reconcile.
- **Every DB op runs on dockerized PG.** A backend-aware `run_sql`/`load_dump` layer means `cc copy`, `cc restore`, `cc db --extend`, and `cc initdb` all work against a container too (CREATE … TEMPLATE, the Odoo expiry SQL, and dump-streaming via `docker exec -i psql`) — no raw `createdb`/`psql` subprocess. `cc initdb` restores the database into the container; the Odoo filestore copy applies to a native Odoo only.

### Tab completion — native, finally live

- **Replaced the dead argcomplete setup** (it was never actually installed) with generated native completion for **zsh, bash, and fish**. `cc shell install` now writes it into your shell integration, so `cc <TAB>` works on a fresh install.
- **Declarative `complete=` on each argument** (an ORM entity class, a literal verb tuple, or a `CompleteKind`) → a shell-neutral spec → per-shell emitters. Dynamic values (projects, envs, databases via the cache, …) are read from SQLite at TAB time — no Python respawn. Deleted `utils/completers.py` and the name-matching dict; see [`cc completion`](commands/config/completion.md).
- **ORM fix:** `update({"rel_id": None})` now actually clears a many-to-one to NULL (it was silently skipped, which had quietly broken workspace project-unassign).

### Companion

- **Settings parity via schema-render.** `/settings` is generated from the same declarative schema the CLI walks (`setting.schema` RPC → `buildGroups`/`SchemaField`), so CLI and web expose the same keys, with save feedback.
- **Manage workspaces from the web.** `/workspaces` moved from read-only to edit + delete, with each version's **venv** shown read-only on the card. (Filesystem ops — worktree create/consolidate, venv link — stay CLI-only.)
- **Env status badges + live refresh** on project cards; **clear-flags** from the history view; nav cleanup and removal of the dead `cc doctor` reference.
- **Env pages route by id, not name.** Environment names aren't unique across projects, so the companion now addresses env detail pages and every `/api/env/*` call by environment id (`/env/[id]`). This fixes a duplicate-React-key crash in the Cmd+K switcher and the latent bug where two envs sharing a name resolved to the same page. The two name-keyed RPCs (`env.update_by_name`, name-based `env.toggle_pin`) — which only the web used — are gone; both are now id-keyed.

### Internals

- **Docs swept for the single-active model** across concepts, commands, and internals.
- **Retired argcomplete** in favour of native completion (see the `cc completion` POC): the `argcomplete.autocomplete()` call only ever fired under `$_ARGCOMPLETE` (never set, since `cc` is a shell function argcomplete can't hook), so it was dead. Dependency and call removed.
- **Removed `cc new` and the dead model registry.** Module scaffolding leaned on a `models` SQLite table populated only by an unregistered, unreachable `cc auto` command (a brittle regex source-scan) — so the table was always empty and the feature degraded to a thin wrapper over `odoo-bin scaffold`. Dropped `cc new`, the `Models` ORM model, `model_completer`, `get_model_names_for_version`, and the `module_templates/` scaffold assets. (The legacy `models.json` store this descended from was already gone since the SQLite migration.)

## v3.7.0 — June 7, 2026

### R&D workflow — switch foundation

Reworked how `cc switch` handles R&D workspaces (a single multi-repo Odoo checkout: `odoo`, `enterprise`, `design-themes`, `upgrade`, `upgrade-util`).

- **All shared repos now follow the env's branch.** On switch, each repo checks out the env branch wherever it already exists (local / fork / upstream), materializing a tracking branch from the fork when needed. If the branch doesn't exist in a repo, that repo is **left untouched** — no fallback checkout, no auto-created branch.
- **Per-repo remotes resolved by URL**, not by a single workspace-wide remote name. `odoo-dev/*` → fork, `odoo/*` → upstream. This handles inconsistent remote names (`origin` vs `odoo` vs `odoo-dev`) and fork-less repos (e.g. `upgrade`, which only has the upstream) with zero per-workspace config. Both fork and upstream are fetched before rebase, fixing a stale-rebase bug where only the fork was fetched.
- **Every repo is optional.** A workspace missing `enterprise`/`design-themes`/`upgrade`/etc. just skips those repos; non-R&D projects are completely unaffected.
- **`--upgrade-path` now spans both upgrade repos**: `upgrade-util/src` *and* `upgrade/migrations`. Previously only `upgrade-util/src` was emitted because the `upgrade` repo was invisible (the `ODOO_UPGRADE` constant pointed at `upgrade-util`). Split into `ODOO_UPGRADE` (`upgrade`) and `ODOO_UPGRADE_UTIL` (`upgrade-util`).
- **R&D addons path no longer appends the workspace root.** The project path equals the version root in R&D mode, so it was adding a junk trailing entry; the addons set is now exactly the shared repos.

### R&D workflow — environment lifecycle (anti-bloat)

R&D maps one env per ticket, so the env list grows without bound. Environments now carry a lifecycle status so the picker stays short.

- **New `status` on environments**: `active` (default) / `merged` / `archived`. The column is added automatically by the ORM's schema sync — no migration; rows predating it read as `active`.
- **Default switch picker filters to what's live.** `cc switch <project>` (and the no-arg recent picker) now show only `active`, pinned, or recently-used (≤14 days) envs. `archived` is always hidden; `merged` lingers through the grace period (recent/pinned) then drops off. **`cc switch --all` / `-a`** shows everything. If every env is filtered out, switch transparently falls back to showing all rather than claiming the project is empty.
- **Manage status from the CLI**: `cc env archive|activate|merged [project]`, plus a "Status" field in the interactive `cc env edit` menu. Status shows as a badge on `cc env list` cards and in `cc env list --json`.
- **Auto-stale**: two new settings (`env.auto_stale_days`, `env.auto_stale_status`, in `cc config` / `cc setup` under *Environments*). When `days > 0`, each switch retires active envs unused for that long to merged/archived — pinned envs are never touched. `0` disables.
- **Reactivation prompt**: switching onto a merged/archived env (via `--all`, `--env <name>`, or a single-env project) asks whether to set it active again, so the lifecycle isn't a one-way trip.
- New RPCs `env.set_status` and `env.sweep_stale`; `env.find_by_project_name` / `env.get_recent_envs` gain an `include_all` parameter.

### R&D workflow — creation UX

- **Auto-detected workspace**: `cc project add <name>` run inside an R&D workspace now detects it from the current directory — no more `-w`. (Non-R&D dirs are unaffected.)
- **Home repo**: R&D project creation asks which shared repo the module(s) live in (odoo/enterprise/upgrade, only those present are offered) and stores it as `Project.home_repo`. It scopes creation; checkout still follows the branch across all repos.
- **Fork-scoped branch picker**: the branch prompt now lists only the home repo's **fork** (odoo-dev) branches, newest first — your own dev branches, not the upstream's thousands. Fast and relevant; falls back to a manual entry when there's no fork.
- **Dash-safe autocomplete**: fixed the autocomplete breaking when you typed past a `-` (e.g. `master-l10n_…`). prompt_toolkit was treating `-` as a word boundary; completion now matches the whole token. Applies to every `cc` autocomplete prompt (branches, databases, …).

### R&D workflow — workspaces via git worktrees

Stop cloning Odoo once per version. New `cc workspace` actions (backed by the `cc.workspace.worktree` module):

- **`cc workspace create [name]`** — build a new R&D workspace by adding `git worktree`s of each shared repo from an existing version's clones. The worktrees share the source's object store, so a second working area for parallel ticket work costs ~nothing. Creates the new dir (detached at the base branch — `cc switch` moves each repo onto the ticket branch), plus its own `version` + `workspace` rows.
- **`cc workspace consolidate`** — fold duplicate *full* clones of the same repo (the "I cloned odoo per version" situation) into worktrees of one canonical clone, reclaiming the wasted disk. **Reversible and safe**: only clean clones are touched; every branch is copied into the canonical first (divergent ones preserved under a `__cc` suffix); the old clone is *moved* to `<path>.cc-bak` (instant, same-filesystem) and replaced by a worktree — nothing is deleted, and a failed `worktree add` rolls the move back. You reclaim disk by deleting the `.cc-bak` dirs once satisfied.

### R&D workflow — forward-port discovery

A ticket is a `project`; each branch in its forward-port chain is an `env` (carrying its own version + branch). cc now builds that chain for you.

- **`Project.main_branch`** — the ticket's starting branch (e.g. `19.0-fix-issue`), set when you create an R&D project.
- **Auto-discovery on `cc project add`** — after you pick the home repo and main branch, cc scans the fork for the chain (`<target>-<main_branch>-fw`, e.g. `19.1-19.0-fix-issue-fw`, `master-19.0-fix-issue-fw`), resolves each target token against your registered cc versions, and creates one env per (version, branch). Unregistered targets are skipped with a note.
- **`cc env add <ticket> --fw`** (alias `--ports`) — re-scan later when you push a new forward-port; idempotent, only adds what's missing.
- Matching is by stripping the known `-<main>-fw` suffix and resolving the leading token against version names — so `saas-17.4` and multi-hop ports work without a brittle regex. New `cc.workspace.forward_ports` module.

### Companion — control env states from the web

The env lifecycle (active / merged / archived) was CLI-only. The env detail page now has a segmented status control right in the header — click to set the state, with the live value reflected. New `POST /api/env/[name]/status` route (→ `env.set_status`); the env GET now returns `status`.

### Active envs stop hanging

In multi-version mode each version keeps its own active env, and nothing ever expired it — so a saas slot you switched to once kept showing as "active" in `cc status` (cwd-resolved) and the dashboard forever. Now an active slot only counts as active if it was switched **within the current session**: after the most recent `timesheet_eod` that's passed, or "today" when no EOD is set. Cross EOD → it reads inactive (computed, so `cc status` self-heals immediately); switching re-activates. Dead `AppState` slots are also pruned lazily on the next switch (new `env.deactivate_stale`).

### Fixes

- **`cc pr create` now uses the repo's PR template.** It was passing `--body ""`, which overrides `.github/PULL_REQUEST_TEMPLATE.md`. cc now resolves the template (gh's standard locations) and prefills it via `--body-file`, falling back to an empty body only when there's no template.

## v3.6.0 — June 5, 2026

### GitHub integration overhaul

Replaced all raw GitHub API calls with the [`gh` CLI](https://cli.github.com/). Authentication now comes from the OS keyring via `gh auth login` — no more storing a PAT in CC's database.

#### `cc pr` — full PR workflow

The [`cc pr`](commands/git/pr.md) command gains subcommands for the complete PR lifecycle:

- **`cc pr`** — interactive TUI picker of your open PRs (unchanged)
- **`cc pr list`** — table of open PRs
- **`cc pr create [base]`** — create a PR from the current branch (interactive title prompt, `--draft` flag)
- **`cc pr view <number>`** — show PR details, review status, and diff stats
- **`cc pr merge <number>`** — merge with method picker (squash/merge/rebase)
- **`cc pr checkout <number>`** — checkout a PR branch locally
- **`cc pr checks <number>`** — show CI check statuses
- **`cc pr --json`** — JSON output (unchanged)

#### Web companion

- Dashboard code reviews and env CI checks now use `gh` — no PAT required
- Settings page: GitHub section replaced with read-only `gh` auth status
- New `/api/github/status` endpoint for auth state

#### Removed

- `github_pat` and `github_username` settings — deleted by migration v18
- PAT input and classic PAT instructions from the Settings page
- All direct `urllib`/`fetch` calls to `api.github.com`

#### New files

- `src/cc/utils/gh.py` — Python `gh` CLI helper (search, view, create, merge, checkout, checks)
- `web/lib/gh.ts` — TypeScript `gh` CLI helper with type-safe remapping to existing contracts

## v3.5.0 — May 30, 2026

### Web companion redesign

The companion app is rewritten away from the generic shadcn-dashboard look toward a distinctive identity.

- **Typography + layout** — Rubik display font, no Card wrappers, hero-stats pattern (big tabular-nums with small labels), asymmetric compositions, section headers and rows separated by thin borders
- **Shared primitives** — `SectionHeader`, `StatDisplay`, `EnvTag`, `StatusIndicator`, `TimeGauge`, `ActivityStrip` — every page composes from the same vocabulary
- **Shared hooks** — `useAutoRefresh`, `useDebounce`, `useIdle`, `useEvents`
- **All pages redesigned** — Dashboard, Projects, Skills, Health, Timesheet, History, Logs, Databases, Env detail
- **Sidebar** — replaced shadcn `Sidebar` with `AppNav`; collapsible (⌘B), state persisted to `localStorage`, icon-only mode for narrow displays
- **Themes work everywhere** — recharts tooltips, sonner toasts, shadcn tooltip popovers all theme-aware via CSS variables + `color-mix(in oklch, ...)`. Covers `default`, `purple`, `rose`, `green`, `blue`, `amber`, `chronocoder`, `light`, `stone`, `sky`, `sage`.
- **Multi-active environments** — Dashboard now lists every active env, not just the first one
- **Light theme contrast pass** — bumped opacity values that ghosted out on light backgrounds
- **Bug fix** — duplicate envs on Dashboard caused by SQL fanout in `/api/projects` (LEFT JOINs that multiplied rows when a env had multiple `app_state` / `database` / `version` matches). Fixed at the route level + defense-in-depth dedupe in `DashboardClient`.

### Idle screen

A new ambient screen takes over after 10 minutes of inactivity.

- Big glowing **cc** wordmark with slow `text-shadow` pulse, theme-aware glow via `color-mix(in oklch, var(--cc-cyan-400) X%, transparent)`
- Bold tabular-nums clock (HH:MM with blinking colon, seconds in smaller superscript)
- Twinkling background stars + a single CRT scanline that sweeps top-to-bottom
- Rotating CLI command tips (23 entries) that fade in/out every 7 seconds
- DVD-screensaver easter egg (1-in-6 chance per activation, or force with `Shift+D` twice) with corner-hit detection and a flash on every corner hit
- Manual triggers for testing: `Shift+I` twice, or `window.dispatchEvent(new Event("cc:idle"))`
- Wakes on any input

### IDE writer plugin system

cc's editor integration is now pluggable instead of hardcoded.

- New `IdeWriter` interface in `cc.ide` — four methods: `name`, `detect`, `setup`, `apply`
- New `CcState` dataclass — stable contract passed to writers (workspace path, env, db, branch, version, odoo_bin, port, addons, modules, upgrade_path, python_path)
- **Built-in writers**: VSCode + Cursor (out of the box). Anything else is a plugin.
- **Setup vs apply split** — `cc switch` only writes `settings.json` (database, addons, modules, ports, Python interpreter). Editor templates like `launch.json` are written once via `cc ide setup` and never touched again, so user customizations survive every switch.
- **New `cc ide` command** — `cc ide list` shows registered writers + which are active; `cc ide setup` writes templates for the active version
- **`cc workspace add`** — prompts to run `cc ide setup` when the new workspace is linked to a version with a path
- **Plugin discovery** — entry-point group `cc.ide_writers` for `pip install …` plugins, or drop a `.py` file in `~/.cc-cli/ide_writers/`
- **Removed** — the inline `_update_vscode_*` methods from `switch_command.py`, the `_update_config` PyCharm/`.odoorc` path (which never did real PyCharm integration anyway), and the now-unused `odoo_config_path` setting + its detector. PyCharm is now a plugin opportunity.

See [IDE Writers](concepts/ide-writers.md) for the concept and [`cc ide`](commands/config/ide.md) for the new command.

### Sync onboarding

Configuring a new device for sync used to be a manual, error-prone `.env` edit with no feedback until the first push failed.

- **New `cc sync setup`** — interactive credential setup for a client device. Prompts for the server URL + API key (pre-filled from existing env/settings), verifies them against the server (reachability + a real authenticated probe), and only then writes `~/.cc-cli/.env` with `600` permissions. Refuses to save a key the server rejects, and preserves any unrelated lines already in the file.
- **Clearer auth failures** — a rejected API key on `push`/`pull` now prints an actionable message (the key isn't registered on the server; run `cc sync setup`) instead of dumping a urllib traceback through the transaction-rollback handler.
- **`cc sync register` warning** — now states explicitly that registering on a client only creates a *local* key; a remote server only accepts keys registered on the server itself, planted on the client via `cc sync setup`. This was the trap behind a confusing `403 Invalid API key` when a laptop with no `.env` silently fell back to a stale `sync.api_key` setting.
- **Fixed `synced_at` never being written** — every syncable model had a `synced_at` column that nothing ever set. Two consequences, both fixed: `cc sync status` reported the *entire* stamped dataset as "pending" forever (regardless of what the server already had), and `cc sync pull --since <T>` returned **zero rows always** (`synced_at > T` is false when `synced_at` is `NULL`), silently breaking incremental sync. Now the receiving side stamps `synced_at` on every ingested row, and a successful push stamps the rows it sent (new `sync.mark_synced` RPC). Status tells the truth and `--since` works.

### License

Changed from MIT to **AGPL-3.0-only**. If you fork cc and run a modified version as a network service, your changes must be made available to users under the same license.

### Mac keyboard shortcuts

- Fixed: notes editor was wired to `Alt+N`, which on Mac is a dead key (Option+N produces `˜` for `ñ`, not `n`). Now `⌘E` (works on both platforms).
- Added: `⌘B` to collapse the sidebar.

### Misc

- `cc workspace add` now prompts to write IDE templates for the linked version's path
- Env detail page: env name → semibold, CLOC rows have breathing room (ml/mr 3), tickets `+` button visible
- `cc ide` available as a CLI command for IDE plugin management
- Dashboard fixed: duplicate envs no longer rendered, project/env name dedup when they match (`acme / acme` → just `acme`)
- Project card branch names visible across all themes (was `text-muted-foreground/20`, now full token)
- AppNav version badge visible across all themes (was `/25`, now full token)
- Fixed: auto-update checker triggered a false-positive "Update available" notification on any branch whose `HEAD` differed from `origin/main`, including feature branches sitting *ahead* of main. Now flags only when `origin/main` contains commits not reachable from `HEAD` (the real "behind" case).
- Fixed: shell integration called `cc daemon start --quiet` and `cc daemon status --quiet` but the flag didn't exist, causing argparse to exit 2 on every new shell session (visible as `[N] + PID exit 2 …daemon start…`). `cc daemon` now accepts `-q/--quiet`. As a bonus, `daemon status --quiet` now exits non-zero when the daemon is stopped, so the shell integration's `status || start` conditional actually works (previously status always exited 0, so the conditional never reached `start`).

## v3.4.0 — May 28, 2026

### Installer v2 + UX polish

New installer that works on any system with Python 3.10+ — no pyenv, no system pollution, no reinstalling per Python version.

#### Install

```bash
git clone https://github.com/Chrono-Coder/cc.git && cd cc
./install.sh        # base install
./install.sh --sync # with sync plugin
```

cc installs into its own venv at `~/.cc-cli/venv`. A shell wrapper at `~/.cc-cli/bin/_cc_internal` always points to it, regardless of which Python or pyenv version is active.

#### Highlights

- **Isolated venv** — no `pip install` into system Python, no `--break-system-packages`
- **Upgrade-safe** — detects old pip installs, removes them, cleans stale `.zshrc` entries, regenerates shell integration with correct paths
- **Bash support** — shell integration now works with zsh, bash, and fish
- **Symlink-safe** — handles symlinked dotfiles (e.g. `~/.zshrc → ~/dotfiles/zsh/zshrc`)
- **`cc` with no args** — ASCII logo + getting started guide instead of raw argparse help
- **Spinners everywhere** — [`cc backup`](commands/db/backup.md) create/restore, [`cc sync`](commands/sync.md) push/pull, [`cc cloc`](commands/project/cloc.md), [`cc web`](commands/web.md) build all show progress
- **Clean TUI exits** — Ctrl+C and selection no longer leave cut boxes on screen
- **Narrow terminal support** — env selector falls back to single-pane layout
- **launch.json merge** — cc appends its `CC: Odoo` and `CC: Odoo [test]` configs instead of replacing the file; existing user configs preserved
- **[`cc env edit`](commands/project/env.md)** — now includes Branch, Version, GitHub URL, Notes, Project path
- **Error messages guide you** — every error tells you what to do next

#### Setup wizard improvements

- Asks for your Odoo root directory instead of scanning from `$HOME`
- Auto-detects git branches and saves them per version
- Path and number prompts retry on invalid input instead of silently skipping
- Prints a summary of what was configured at the end

#### Removed

- `installer.sh` — replaced by `install.sh`
- `cc upgrade` command — legacy v1 → v2 migration, no longer needed

## v3.3.0 — May 26, 2026

### Multi-device sync (plugin)

Sync cc data across multiple machines through a central server. Install with `pip install cc-cli[sync]` — the base package is unaffected.

- **Encrypted transport** — AES-256-GCM on all sync payloads, key derived from device API key
- **Auto-sync** — background push/pull every 5 minutes when configured
- **FK resolution** — foreign keys resolve by natural key (project name, version name), not raw IDs
- **`cc sync resolve`** — remaps version references and project paths on new devices, auto-clones missing repos via SSH
- **`.env` file** — `~/.cc-cli/.env` loaded on startup for secrets (`CC_SERVER`, `CC_API_KEY`)
- **Secret filtering** — `github_pat` and sync credentials never leave the device
- **Intel sync** — repository, skill_tag, knowledge_index tables included

#### Setup

1. Install `pip install cc-cli[sync]` on server and each client
2. Start the sync server: `python -m cc.sync.http_server --port 9100`
3. Register devices: `cc sync register --name laptop` (run on the server)
4. Configure clients in `~/.cc-cli/.env` with `CC_SERVER` and `CC_API_KEY`
5. Restart [daemon](commands/daemon/README.md): `cc daemon restart` — auto-sync starts immediately
6. First sync on a new device: `cc sync resolve` to fix paths (once per device)

#### Synced tables

version, setting, database, project, environment, switch_log, backup, repository, skill_tag, knowledge_index

Systemd service files included in `deploy/` for running the sync server and web companion on a Raspberry Pi.

## v3.2.0 — May 24, 2026

### Rich output migration

Every cc output surface migrated to a themed [rich](https://github.com/Textualize/rich) console. The legacy `Colors` class and `halo` dependency are removed.

- **Themed console singleton** with semantic styles (`primary`, `branch`, `db`, `success`, `warning`, `error`, `muted`)
- **Shared builders** — `themed_table()` and `env_card()` for consistent output
- **All commands themed** — [`cc stat`](commands/stat.md), [`cc env list`](commands/project/env.md), [`cc project`](commands/project/README.md), [`cc time`](commands/time.md), [`cc cloc`](commands/project/cloc.md), [`cc switch`](commands/switch.md), [`cc intel`](commands/intel.md), [`cc config`](commands/config/README.md), and more
- **Rounded frames** on all prompt_toolkit TUIs (selector, multiselect, confirm, [theme](commands/config/theme.md) picker)
- **Logger rewritten** — debug mode uses `RichHandler`, normal mode uses a lightweight handler
- **Themes pruned 7 to 4** — `default`, `purple`, `chronocoder`, `custom`
- **Config decomposed** — 1200-line config command split into domain modules ([shell](commands/config/shell.md) installer, [theme](commands/config/theme.md) picker, [workspace](commands/workspace.md) registration, [venv](commands/config/venv.md) linker, [config](commands/config/README.md) schema)
- **CI workflow** — GitHub Actions for pytest + install + web build

## v3.1.1 — May 24, 2026

- Removed TC001 device integration
- Fixed `launch.json` template — `-u` arg now uses `${config:cc.initMode}`

## v3.1.0 — May 18, 2026

### Intel, workspaces, and CLI improvements

- **Skill telemetry** — [`cc intel scan`](commands/intel.md), [`cc reindex`](commands/reindex.md), `/skills` web page; scans git repos for skill patterns (models, wizards, controllers, etc.) and builds a knowledge index
- **[Workspaces](commands/workspace.md)** — group projects under an Odoo version; R&D mode auto-checkouts env branches in shared Odoo repos with fetch + rebase
- **Virtual projects** — time-tracking-only projects with no filesystem
- **[`cc venv`](commands/config/venv.md)** — interactive TUI for pyenv virtualenv management
- **Database pools** — [`cc db --link/--unlink`](commands/db/README.md) to manage a pool of databases per environment
- **`--json` flag** on [`cc stat`](commands/stat.md), [`cc time`](commands/time.md), [`cc env list`](commands/project/env.md), [`cc pr`](commands/git/pr.md)
- **[`cc switch --env`](commands/switch.md) autocomplete** — tab completion for environment names
- **[`cc branch`](commands/git/branch.md) auto-checkout** — checks out branch when updating the active environment
- **[`cc cloc -a`](commands/project/cloc.md)** — CLOC only active modules, skip picker
- **ORM M2M support** — `Property(many2many=...)` with junction tables

## v3.0.1 — May 6, 2026

- Pub/sub event bus for real-time [web](commands/web.md) companion updates
- Pre/post [switch](commands/switch.md) hooks — scripts in `~/.cc-cli/hooks/`, stdout eval'd in parent shell
- [Daemon](commands/daemon/README.md) auto-start with exponential backoff
- [`cc module -i`](commands/project/module.md) mode toggle
- O2M create command types 4 and 6

## v3.0.0 — May 3, 2026

### Daemon architecture

- **[Daemon](commands/daemon/README.md) process** — long-running on Unix socket (`~/.cc-cli/cc.sock`), JSON-RPC 2.0
- **Single-writer guarantee** — all writes go through the daemon; CLI, [web](commands/web.md), and extensions are clients
- **Service layer** — business logic in `src/cc/services/`, each module maps to an RPC namespace
- **`@rpc_method` decorator** — type validation, introspection registry
- **`system.describe`** — full RPC schema with semantic hints
- **Real-time SSE** — [web](commands/web.md) companion subscribes to state changes
- **Postgres service** — `pg.list_databases`, `pg.get_db_stats`, `pg.drop_db` with caching and parallel connections
- **RPC request log** — [`cc logs`](commands/daemon/logs.md) to view `~/.cc-cli/logs/rpc.log`
- **77 tests** covering services, router, DTOs, and RPC contracts

## v2.4.0 — May 2, 2026

- **[`cc backup`](commands/db/backup.md)** — named PostgreSQL snapshots with create, list, restore, delete
- **[`cc tunnel`](commands/tunnel.md)** — SSH tunnel to Odoo.sh PostgreSQL databases
- **CLI theming** — 5 named color palettes via [`cc theme`](commands/config/theme.md)
- **Notes editor** — per-environment WYSIWYG (TipTap) with rich text
- **Ticket IDs** — multiple per environment, shown as pill badges
- **Quick-switcher** — Cmd+K / Ctrl+K fuzzy search across all environments
- **Pin/star** — favourite environments pinned to top of selectors
- **Collapsible sidebar** — icon-only mode with persisted state
- **Web theming** — 10 themes with full light mode support

## v2.3.0 — April 3, 2026

- **shadcn/ui migration** — all companion components migrated
- **Suspense streaming** — slow sections (GitHub API, health checks) stream independently
- **History pagination** — 10 days per page with URL navigation
- **[`cc initdb`](commands/db/init.md) overhaul** — recursive file picker with date sorting
- **Shared formatting** — `lib/fmt.ts` consolidates `timeAgo`, `fmtDuration`, etc.

## v2.2.0 — March 28, 2026

### CC Companion

- **Next.js [web](commands/web.md) dashboard** — reads directly from `~/.cc-cli/cc_cli.db`
- **Dashboard** — active environments, GitHub code reviews
- **[Projects](commands/project/README.md) page** — environment grid with search, copy [`cc switch`](commands/switch.md), GitHub/SH links
- **[Environment](commands/project/env.md) detail** — version/branch/database pills, CI checks, CLOC, modules, notes
- **[Timesheet](commands/time.md) page** — grouped bar chart, pie chart, ranked totals, date range selector
- **History page** — switch log grouped by day with delete and undo
- **Health page** — data quality checks with hints to run `cc doctor`
- **[Settings](commands/config/README.md) page** — GitHub PAT, Odoo SH session sync
- **`cc doctor`** — 9 data-quality checks with interactive auto-fix
- **Postgres health** — untracked DBs, missing DBs, idle DBs with inline drop

## v2.1.0 — March 26, 2026

- **Single-repo mode** — one Odoo directory with branch checkouts per version
- **Auto-[fetch](commands/git/fetch.md)** — background `git fetch` on [switch](commands/switch.md) when interval elapsed
- **pyenv integration** — auto-link virtualenvs per Odoo version via [`cc venv`](commands/config/venv.md)
- **[Multi-version mode](concepts/multi-version-mode.md)** — one active project per Odoo version
- **[Timesheet](commands/time.md)** (`cc time`) — automatic session tracking with flag system
- **[`cc cloc`](commands/project/cloc.md)** — lines of code per module
- **Update notifier** — background version check on [switch](commands/switch.md)

## v2.0.0 — February 8, 2026

### The rewrite

- Pip-installable package
- SQLite replaces `storage.json`
- Custom prompt_toolkit prompter (rounded frames, themed selectors)
- Data moved to `~/.cc-cli/`
- Daddy shell removed
- Questionary dependency removed
- ORM with one-to-many relations

## v1.0.0 — March 16, 2025

### First release

- [`cc switch`](commands/switch.md) — project/environment switching with fuzzy directory search
- [`cc config`](commands/config/README.md) — Odoo version configuration
- [`cc initdb`](commands/db/init.md) — database initialization from dump files
- [`cc module`](commands/project/module.md) — install/upgrade Odoo modules
- [`cc fetch`](commands/git/fetch.md) — update all Odoo version repos
- [`cc cd`](commands/cd.md) — navigate to project directory
- [`cc db`](commands/db/README.md) — database switching
- [`cc copy`](commands/db/copy.md) / [`cc restore`](commands/db/restore.md) — database dump and restore
- [`cc cloc`](commands/project/cloc.md) — lines of code counter
- [`cc project`](commands/project/README.md) — project management
- [`cc ticket`](commands/ticket.md) / [`cc github`](commands/git/github.md) / [`cc sh`](commands/sh.md) — quick-open external tools
- VSCode extension integration
- Argcomplete tab completion

## Pre-release — Sep 2024 to Feb 2025

Initial development under the `chronofeldyx` org. Parser skeleton, command inheritance system, unified fuzzy directory search, the "daddy shell" experiment, and iterative feature building that led to v1.0.

See [History](history.md) for the full story.
