# cc

CLI + web companion for Odoo developers. SQLite-backed daemon process
exposing JSON-RPC over Unix socket (`~/.cc-cli/cc.sock`). Next.js
companion (`web/`) talks to the same daemon.

## Architecture

```
CLI / Web / VSCode Extension
    ↓ JSON-RPC 2.0 (Unix socket)
CC Daemon  (~/.cc-cli/cc.sock)
    ↓
Service Layer  (src/cc/services/)
    ↓
ORM  (src/cc/base/arm/)
    ↓
SQLite  (~/.cc-cli/cc_cli.db)
```

**CQRS-lite (hard rule):**
- Writes → daemon RPC only (`cc.daemon.client.call("ns.method", **kwargs)`)
- Reads → direct ORM/SQLite (WAL handles concurrent readers; no benefit routing through daemon)

## Dev commands

```bash
pip install -e .          # the whole CLI (intel/rnd/web are built in, not plugins)
cc daemon start           # daemon (needs socket)
cd web && npm run dev      # companion at :3000 (or `cc web` to build + serve)
python -m pytest tests/   # never touches real DB
```

## System map

### Daemon (`src/cc/daemon/`)

| File | Role |
|------|------|
| `server.py` | Unix socket listener, JSON-RPC 2.0, one thread/conn, warms ORM on startup |
| `router.py` | `"namespace.fn"` → service dispatch, validates params+types |
| `rpc_method.py` | `@rpc_method` decorator — captures signature, attaches `_rpc_required` |
| `client.py` | `call(method, **params)` — auto-starts daemon if not running |
| `db_sync.py` | background thread: `database.reconcile()` on startup + every 120s (PG metadata → SQLite cache) |

### Services (`src/cc/services/`)

| File | Namespace | Purpose |
|------|-----------|---------|
| `environment.py` | `env` | switch, create, delete, update, toggle_pin, find, recent envs |
| `project.py` | `project` | CRUD projects |
| `database.py` | `database` | CRUD + lifecycle: drop/rename/copy/restore/extend/init_from_dump (all backend-routed), reconcile (PG→cache); SQL-interpolated names validated, restore verifies the template exists live before dropping |
| `workspace.py` | `workspace` | CRUD workspaces, assign projects |
| `timesheet.py` | `timesheet` | explicit spans: `create_entry` (manual), `update_entry` (start/end/note), `delete_entry`, punch_out, clear_flags, and `entries(start,end)` — THE shared resolution (auto gap-baseline + manual/edited-auto authoritative, human-touched-wins, no double-count) used by both CLI and web |
| `version.py` | `version` | CRUD Odoo versions |
| `backup.py` | `backup` | named DB snapshots |
| `setting.py` | `setting` | K/V config store |
| `system.py` | `system` | describe (schema introspection) |
| `pg.py` | `pg` | list DBs, stats, last login, drop/rename, database_exists, check — ThreadPoolExecutor; connects via `pg_connect`. **Backend seam:** `run_sql`/`load_dump`/`database_exists` route to direct psycopg2 or docker-exec via `_backend()` (probed once, cached; `reset_backend()` clears it when `pg.connection`/`pg.container` changes) |
| `pg_connect.py` | — | self-discovering PG connector (DSN/socket/TCP probe, cached); `cc db check`; `reset()` also clears pg's backend cache |
| `pg_docker.py` | — | dockerized PG via `docker exec psql` (unpublished-port containers) — discover/gather/drop/rename/exec_sql/load_dump/db_exists |
| `sync.py` | `sync` | device registration, push/pull sync, FK resolution by natural key |
| `intel.py` | `intel` | code-intel: scan/add-repo, reindex (git-history crawl), search, who-knows, skills |

### Sync module (`src/cc/sync/`)

| File | Role |
|------|------|
| `http_server.py` | Standalone HTTP server exposing `sync.*` RPC (runs on central Pi) |
| `http_client.py` | JSON-RPC client — reads `CC_SERVER`/`CC_API_KEY` from env or settings |
| `auto.py` | Background thread — periodic push/pull cycle (5 min default) |

### Events (`src/cc/events/`)

In-process **event bus** decoupling core commands from feature reactions
(`bus.emit("switch.before", SwitchEvent(...))`). Handlers run **CLI-side** (so
they may prompt), in priority order, and write via daemon RPC; a `*.before`
handler raising `EventCancelled` aborts the command, any other exception is
isolated. Discovery: handlers are imported from `cc.events.handlers` (its
`__init__` imports each handler module). Payloads are frozen, additive-only
dataclasses (like `CcState`). The timesheet punch-out on switch lives here
(`handlers/timesheet.py`), and the R&D switch-rebase in `handlers/rnd.py`
(setting-gated) — no longer hard-wired into `switch_command`.

### Feature modules: intel, rnd, web (in core, setting-gated)

cc ships as **one package** — intel/rnd/web are built in, not separately-installed
plugins. (There was an entry-point plugin system in 3.10; it was removed once the
features proved generic/internal enough to live in core. The lever now is a
**setting**, not install/uninstall.) Each former plugin lives in normal core homes
and is registered the normal way:

| Feature | Commands | RPC / models | Domain code | On-switch handler (gated) |
|---------|----------|--------------|-------------|---------------------------|
| **intel** | `cc intel`, `cc reindex` (`commands/intel/`) | `services/intel.py` (`intel`), models in `arm/intel.py` | `cc/intel/` (indexer, storage, language packs) | `daemon/handlers/reindex.py` — gated by `intel.auto_reindex` |
| **rnd** | `cc rnd create/consolidate/project/fw` (`commands/rnd/`) | — | `cc/rnd/` (worktree, forward_ports) | `events/handlers/rnd.py` — self-gates to R&D workspaces + `rnd.auto_rebase` |
| **web** | `cc web` (`commands/system/web_command.py`) | reads daemon/SQLite | `web/` (Next.js, repo root) | — |

The web `/skills` page reads intel's tables/RPC. The daemon event bus
(`cc.daemon.event_bus`) publishes to both SSE subscribers (web) and in-process
`@on_event` handlers (`daemon/handlers/`) — distinct from the CLI bus (`cc.events`,
which may prompt).

### Commands (`src/cc/commands/`)

CLI surface is **noun-grouped** (`cc <group> <verb>`, 3.9). A command's `group`
class attr nests it under `cc <group>`; a command whose `name` *equals* its
`group` is the group ROOT — bare `cc <group>` runs it (e.g. `cc config`).
`group`/`name` resolve as **own** attrs (`__dict__`) so a base command never
leaks its group/name to subclasses that extend it. Rootless groups print help on
bare invocation. Mechanism in `cc.base.command` (`_ensure_group`, `_GroupHandler`,
group-aware `build_classes`).

| Surface | Verbs |
|---------|-------|
| flat (hot-path) | `switch` · `cd` · `stat` · `setup` · `workspace` (internal action: add/list/edit/open/assign/remove) |
| `cc db` | use · list · drop · init · copy · restore · backup · rename · link · unlink · extend · check |
| `cc git` | branch · fetch · github · pr (list/create/view/merge/checkout/checks via `gh`) |
| `cc config` | *(bare = settings picker)* · ide · venv · theme · shell · completion · reset |
| `cc daemon` | start · stop · restart · status · logs |
| `cc project` | create · list · delete · keep · env `<verb>` · cloc · module · open |
| `cc rnd` | create · consolidate · project · fw |
| flat | `time` (action: start/end/edit/delete/review) · sync · sh · psx · ticket · web · intel · reindex (tunnel hidden) |

Source folders (`commands/<group>/`) are code organization, **not** the CLI shape:
`project/`, `database/`, `git/`, `odoo/`, `system/`. Kitchen-sink commands were
exploded into verbs (db, project) or kept an internal action positional that
nests cleanly (`cc git pr <action>`, `cc project env <action>`, `cc workspace …`).

### Domain modules

CLI commands delegate to focused domain modules — one home per concern.
Both the standalone command (`cc shell install`) and the wizard step
(`cc setup`) share the same implementation.

| Module | Owns | Used by |
|--------|------|---------|
| `cc.config.schema` | Declarative settings registry (key, label, type, default) | `cc setup` walks it, `cc config` picker reads it |
| `cc.config.wizard` | Sequenced `cc setup` orchestration | `cc setup` |
| `cc.shell.installer` | Detect / install zsh + fish integration files | `cc shell install`, `cc setup` |
| `cc.theme.picker` | Theme + custom-color TUIs + apply | `cc theme`, `cc setup` |
| `cc.workspace.registration` | Discover Odoo installs, register versions, ensure workspaces | `cc workspace add`, `cc setup` |
| `cc.rnd.worktree` | Git-worktree discovery/create/consolidate for R&D workspaces (no re-clone; reversible dedup) | `cc rnd create`, `cc rnd consolidate` |
| `cc.rnd.forward_ports` | Match a ticket's forward-port branches (`{target}-{main}-fw`) → (version, branch) chain | `cc rnd project`, `cc rnd fw` |
| `cc.venv.linker` | pyenv link/create + odoo requirements install | `cc venv`, `cc setup`, `cc config --set-pyenv` |
| `cc.completion` | parser → shell-neutral spec → zsh/bash/fish emitters; declarative `complete=` on Arguments | `cc completion`, `cc shell install` |

### ORM models (`src/cc/base/arm/`)

| Model | Key fields |
|-------|-----------|
| `Environment` | name, project_id, branch, db_name, addons_path, last_used_at, pinned, notes, status (active/merged/archived) |
| `Project` | name, is_virtual, no_auto_archive (exempt from sweep_stale), workspace_id, home_repo (R&D: odoo/enterprise/upgrade), main_branch (R&D anchor) |
| `Workspace` | name, path, is_rnd, version_id, project_ids |
| `Version` | name, path, port, branch |
| `SwitchLog` | environment_id, switched_at, **ended_at, note, source (auto/manual), edited** (3.11 explicit spans; NULL ended_at = open/gap-derived auto row) |
| `Setting` | name, value (K/V) |
| `Database` | name, clone_db_id, sync_id; PG cache: in_pg, size_bytes, last_login, is_odoo, last_synced_at |
| `Backup` | name, env_name, db_name, file_path, size_bytes |
| `AppState` | environment_id (the active env; single row by default, or one per version when `multi_version_mode` is on — 3.11) |
| `Device` | name, api_key, last_seen_at, created_at (sync device registration) |
| `DevicePath` | device_id, project_id, local_path (per-device project paths for sync) |
| `Module` | name, environment_id (module rows per env) |

DTOs (not ORM): `src/cc/services/dto.py` — `EnvStatusDTO`, `ProjectStatusDTO`,
`EnvDetailDTO`, `SwitchResultDTO` (structured returns the CLI deserializes).

**Active env + timesheet (3.11) — navigation decoupled from accounting.**
*Navigation:* single active env by default; with `multi_version_mode` on,
`env.switch`/`_resolve_active_env` keep one active slot **per Odoo version**,
resolved from the cwd's version (so two versions stay live in two editors).
*Accounting:* `cc switch` appends a `source="auto"` SwitchLog span (gap-based
baseline) unless `timesheet_mode == "manual"`. `cc time start/end` add explicit
manual spans (notes, overlap allowed); editing any span (incl. auto) makes it
authoritative. `timesheet.entries()` resolves the two layers (human-touched
wins) for both `cc time` and the web `/history`.

### Web companion (`web/`, Next.js at the repo root)

| Route | Purpose |
|-------|---------|
| `/` | Dashboard — active envs + GitHub PRs |
| `/projects` | Project grid |
| `/env/[id]` | Env detail — meta, CI, CLOC, notes |
| `/timesheet` | Bar+pie charts |
| `/history` | Switch log with inline edit |
| `/skills` | Skill telemetry — charts, search, domains |
| `/health` | Health checks |
| `/logs` | Daemon log viewer |
| `/settings` | Config (GitHub, SH, IDE, timesheet) |
| `/workspaces` | Workspace management |
| `/databases` | Database grid |
| `/versions` | Odoo version management |

Paths are under `web/`. Key libs: `lib/rpc.ts` (daemon socket), `lib/db.ts` (read-only SQLite), `lib/serverData.ts` (direct DB reads shared by API routes + server components — never self-fetch a route during SSR), `lib/fmt.ts`, `lib/gh.ts` (`gh` CLI wrapper). `cc web` (`commands/system/web_command.py`) runs `npm install` + `npm run build` + `next start` in `web/` in place (cc always runs from a checkout; node_modules/.next stay gitignored under `web/`). No `output: standalone` — it exits immediately on Next 16 + Node 26.

### Key paths

| Constant | Path |
|----------|------|
| DB | `~/.cc-cli/cc_cli.db` |
| Socket | `~/.cc-cli/cc.sock` |
| Logs | `~/.cc-cli/logs/cc.log`, `rpc.log` |
| PID | `~/.cc-cli/cc-daemon.pid` |
| Shell integration | `~/.cc-cli/shell/cc.zsh` |

### IDE settings contract

`VSCodeWriter.apply()` writes these keys to `<workspace>/.vscode/settings.json` on every `cc switch`. Stable contract — additive only.

| Key | Value |
|-----|-------|
| `cc.odooBin` | Path to `odoo-bin` |
| `cc.port` | Active version's port |
| `cc.database` | Active database name |
| `cc.addonsPath` | Resolved addons paths (comma-separated) |
| `cc.modules` | Active modules (comma-separated) |
| `cc.upgradePath` | Path to upgrade `src/` |
| `cc.projectPath` | Filesystem path to the active project |
| `cc.envName` | Active environment name |
| `cc.projectName` | Active project name |
| `cc.initMode` | `"-i"` or `"-u"` (defaults to `-u`) |
| `python.defaultInterpreterPath` | pyenv-resolved Python interpreter |

## Conventions

### Migrations

Append-only. Never reorder, never mutate existing entries. Next sequential number.

**Adding a column? Don't write a migration.** On startup `BaseEntity.sync_schema()`
runs *before* migrations and auto-`ALTER TABLE ... ADD COLUMN` for any new
`Property` (and rebuilds the table to drop removed ones). So a new field is just a
new `Property` — the column appears automatically. An `ADD COLUMN` migration would
run *after* sync_schema and fail as a duplicate. That's why every migration is an
index / backfill / new table / data change — never `ADD COLUMN`.

Defaults are applied in Python on `create()` (`_apply_default_field_values`), not
as SQL `DEFAULT`, so the auto-added column is nullable and existing rows read
`NULL`. New fields must treat `NULL` as the default (e.g. `env.status or "active"`).

### RPC services

- Decorate with `@rpc_method` — undecorated functions are blocked by router
- Register namespace in `src/cc/daemon/router.py:_REGISTRY`
- Daemon warms ORM on startup — add new model imports to `server.py`

### CLI commands

- Subclass `Command`, register in `commands/<group>/__init__.py`
- Nest under a noun group with `group = "<name>"` — an **own** attr: declare it
  explicitly even on subclasses (it does NOT inherit, by design). `name == group`
  makes the command the group root (bare `cc <group>` runs it). A base shared by
  several commands (e.g. `ProjectCommand`) must have **no own `name`** so it isn't
  registered as a command itself.
- All writes go through `call()` — never write to DB directly from CLI
- React to core actions via the event bus (`@subscribe("switch.before")`), not by
  importing a feature into hot-path commands — this keeps `switch` lean and features
  independently togglable (a handler self-gates or checks its setting).

### ORM

- `Property` descriptors for typed columns
- Constraints via `_constraints = [UniqueConstraint(...)]`
- `save()` / `delete()` / `find()` / `find_all()` on BaseEntity
- Adding a `Property` auto-creates its column via `sync_schema()` on startup — no
  migration (see Migrations above). Removing one rebuilds the table and drops it.

### CLI output (rich)

- Themed Console singleton: `from cc.utils.console import get_console`
- Semantic styles: `primary`, `branch`, `db`, `success`, `warning`, `error`, `muted`, `header`, `info`, `heading` (bold primary), `bg_accent`
- Tables: `from cc.utils.panels import themed_table` — never construct `rich.table.Table(...)` directly. Defaults: `box.ROUNDED`, `heading` title + header, `primary` borders. Override via kwargs.
- Env card panel: `from cc.utils.panels import env_card` — pass a normalized env dict
- `Colors` (legacy ANSI) is being phased out; new code goes through the console singleton

### Web companion

- Next.js 16 app router — read `node_modules/next/dist/docs/01-app/` for route handler API
- Theme awareness: `useTheme().isLight` → conditional chart colors (see `TimesheetClient.tsx`)
- SSE events: `useEvents()` hook for real-time state subscriptions
- Writes → `/api/*` routes → `rpcCall()` → daemon socket
- Reads → direct SQLite via `web/lib/db.ts`
- Auth: `web/proxy.ts` gates every request — local-Host allowlist, foreign-Origin
  rejection on mutations, and a token from `~/.cc-cli/web.token` (`cc web` generates
  it and opens the browser with `?token=`; SSR self-fetches send it as a Bearer
  header, see `lib/api.ts`). `CC_WEB_ALLOW_REMOTE=1` opts out of the Host check for
  trusted-LAN deployments (`deploy/cc-web.service`)

### Commits

- Signed commits required — never `--no-gpg-sign`
- Worktrees may fail to sign; work in canonical dir if needed
- The cc repo's `origin` is SSH (`git@github.com:…`); the background update-check (`utils/update_checker.py`) and any auto-`git pull` run fully non-interactive (`GIT_TERMINAL_PROMPT=0`, cleared credential helper) so they never pop the OS keychain — keep them that way

## Hard rules

1. **Never call `cr.commit()`** in business logic
2. **Never route reads through daemon** — direct ORM/SQLite only
3. **Migrations are immutable once merged** — append new, never edit old
4. **No raw SQL in services** — use ORM. SQL only in migrations or explicit performance paths
5. **Web writes always go through RPC** — never import/use `db.ts` for mutations
6. **Keep this file current** — when adding new services, commands, models, or web routes, update the system map tables above to reflect the change
