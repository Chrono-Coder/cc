# Under the Hood

CC is built entirely in Python with no heavy frameworks. Here's what's running beneath the surface.

## Architecture (v4.0)

```
┌──────────────────────────────────────────────────────┐
│  Clients                                             │
│  CLI (cc)  ·  Web app (:3000)  ·  VSCode extension   │
└──────────────┬──────────────────────────┬────────────┘
               │ Unix socket              │ direct SQLite
               │ JSON-RPC 2.0             │ reads only
               ↓                          │
┌──────────────────────────────┐          │
│  CC Daemon                   │          │
│  ~/.cc-cli/cc.sock           │          │
│  src/cc/daemon/server.py     │          │
│  src/cc/daemon/router.py     │          │
└──────────────┬───────────────┘          │
               │                          │
               ↓                          │
┌──────────────────────────────┐          │
│  Service Layer               │          │
│  src/cc/services/            │          │
└──────────────┬───────────────┘          │
               │                          │
               ↓                          ↓
┌──────────────────────────────────────────────────────┐
│  ORM  ·  ~/.cc-cli/cc_cli.db (SQLite)                │
│  Single writer: daemon only                          │
└──────────────────────────────────────────────────────┘
```

**Core rule (CQRS-lite):** writes go through the daemon, reads go direct.

### Why not RPC for reads?

CC deliberately separates reads and writes at the transport level — a lightweight form of [CQRS](https://martinfowler.com/bliki/CQRS.html):

- **Writes via daemon** — serialises concurrent writes from the CLI, web app, and VSCode extension. Without this, two processes writing to SQLite simultaneously can corrupt state.
- **Reads direct** — SQLite handles concurrent readers natively (WAL mode). A socket round-trip for a read adds latency for zero benefit: `connect → serialise → send → receive → deserialise → close` vs. a direct file read in microseconds. It would also mean any read command hangs for up to 10 seconds if the daemon is slow to start.

The web companion reads directly from the SQLite file (via `better-sqlite3` in `web/lib/db.ts`) for the same reason — it's a local read-only consumer, no coordination needed.

## Daemon

`cc daemon start` launches a background process that listens on a Unix socket (`~/.cc-cli/cc.sock`). It speaks [JSON-RPC 2.0](https://www.jsonrpc.org/specification) — one connection per request, one thread per connection.

The daemon is the **single writer** to `~/.cc-cli/cc_cli.db`. This eliminates write conflicts between the CLI, the web app, and the VSCode extension all running concurrently.

```
~/.cc-cli/
  cc_cli.db         ← all your data
  cc.sock           ← Unix socket (daemon)
  cc-daemon.pid     ← daemon PID
  logs/
    cc.log          ← rotating log file
```

The daemon warms the ORM on startup — first request has zero cold-start cost.

## RPC Protocol

Calls use the method string `"namespace.function"` — e.g. `"env.switch"`, `"timesheet.delete_entry"`. The router maps namespaces to service modules and validates params before dispatch.

```json
→ {"jsonrpc": "2.0", "method": "env.toggle_pin", "params": {"name": "acme-prod"}, "id": 1}
← {"jsonrpc": "2.0", "result": true, "id": 1}
```

All public service functions must be decorated with `@rpc_method`. The decorator captures the function signature at decoration time, records required params and types for validation, and registers the function in the introspection schema. The router rejects undecorated functions with error `-32601`.

### Introspection

```bash
cc api system.describe        # full schema of all registered RPC methods
cc api system.describe_models # ORM model fields, types, and semantic hints
```

Semantic hints (`"datetime"`, `"url"`, `"path"`, `"text"`, `"csv"`) are declared on ORM `Property` fields and surfaced automatically in the schema — useful for external integrations.

## Service Layer

Business logic lives in `src/cc/services/`, one file per domain:

| Namespace | File | Key functions |
| --- | --- | --- |
| `env` | `environment.py` | `switch`, `create`, `delete`, `update`, `toggle_pin`, `find_by_name` |
| `project` | `project.py` | `create`, `delete`, `get_all` |
| `timesheet` | `timesheet.py` | `punch_out`, `update_entry`, `delete_entry`, `clear_flags` |
| `version` | `version.py` | `create`, `upsert`, `update`, `update_port` |
| `database` | `database.py` | `create`, `delete`, `update`, `link_to_env`, `copy`, `restore`, `init_from_dump` |
| `backup` | `backup.py` | `create`, `delete` |
| `setting` | `setting.py` | `upsert` |
| `system` | `system.py` | `describe`, `describe_models`, `health` |
| `intel` | `services/intel.py` | `scan`, `add_repo`, `list_repos`, `reindex`, `reindex_dump`, `search`, `skills` |
| `sync` | `sync.py` | `push`, `pull` (network); enrollment/bookkeeping stay local |

Services return plain Python objects or typed dataclasses (`SwitchResultDTO`, `EnvDetailDTO`). No JSON, no HTTP awareness.

## SQLite Database

All CC data lives in a single SQLite database at `~/.cc-cli/cc_cli.db`.

This includes your projects, environments, versions, databases, modules, settings, app state, and switch logs — everything CC needs to work, stored locally on your machine. No cloud, no external service.

The database is created automatically on first run and survives CC updates since it lives outside the package directory.

## Custom Mini-ORM

CC uses a lightweight ORM built from scratch — no SQLAlchemy, no Django ORM. It lives in `base/arm/` and was designed to feel familiar to anyone who's worked with Odoo's ORM.

Models are defined as Python classes:

```python
class Environment(BaseEntity):
    _name = "environment"

    name        = Property(type=str, unique=True, required=True)
    project_id  = Property(relation="project")
    version_id  = Property(relation="version")
    branch_name = Property(type=str)
    database_id = Property(relation="database")
    module_ids  = Property(one2many="module", inverse_name="environment_id")
```

The ORM handles:
- **Auto schema sync** — `sync_schema()` creates or migrates tables on startup based on model definitions
- **Many-to-one relations** — foreign keys resolved to full objects on access
- **One-to-many relations** — `environment.module_ids` returns an `EntityList`
- **`EntityList`** — a list subclass with `.mapped()`, `.filtered()`, and single-record attribute passthrough (like Odoo's recordset)
- **`search()` / `find_by()`** — domain-based and keyword-based queries
- **`create()` / `update()` / `delete()`** — full CRUD

## Auto Schema Migration

On every startup, CC calls `sync_schema()` which compares the current model definitions against the live SQLite schema and applies any missing columns or tables. No migration files to manage.

## App State

The active project/environment is tracked in an `AppState` model rather than a flag on the project itself. By default it's a singleton — one row pointing at the single active environment (the one you last switched to), replaced on every switch. With [multi-version mode](concepts/multi-version-mode.md) enabled, cc keeps one row per Odoo version (the `version_id` slot), so each version has its own active env.

```
AppState
  environment_id  → which environment is active
  version_id      → which version slot (NULL = single mode)
```

## Shell Integration

`cc switch` needs to change your terminal's working directory — something a subprocess can't do on its own. CC writes shell commands to a named pipe that a small shell function (installed by the installer) reads and executes in the parent shell. That's how `cc cd` and branch checkouts actually work.
