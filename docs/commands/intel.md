# cc intel

Manage the skill telemetry index — discover, register, and list git repositories.

## How It Works

The intel system builds a queryable skill graph from your authored git history. It walks `git log`, parses diffs through language packs (Python, Odoo), and writes structured tags into a local SQLite database.

### Indexing Flow

1. **Register repos** — `cc intel scan` or `cc intel add-repo` adds repos to the `repository` table
2. **Index commits** — `cc reindex` walks each repo's git log (filtered to your author identity), extracts skill tags per commit
3. **Query** — the `/skills` web page reads from the indexed data

### Incremental Updates

Indexing is incremental by default. Each repository tracks `last_indexed_commit_sha` — subsequent runs only process new commits since that point. A full reindex (`cc reindex --full`) re-processes everything from scratch.

### Auto-Reindex on Switch

Every time you run `cc switch`, a background thread checks whether the switched-to project has a registered repository. If it does and the last index is older than **1 hour**, it runs an incremental reindex automatically. This happens in a fire-and-forget daemon thread — it never blocks or slows down the switch.

The auto-reindex:
- Only fires if the project's path matches a registered `Repository` record
- Skips if the repo was indexed within the last hour
- Skips if the repo is disabled (`enabled = false`)
- Errors are silently logged at debug level — never surfaces to the user
- Runs incrementally (only new commits since last indexed SHA)

**Opt out:** run `cc config`, pick "Auto-reindex on switch", set to false.

This means after the initial setup (`cc intel add-repo` + `cc reindex`), your skill data stays current automatically as you work. You never need to manually reindex unless you want a full rebuild or need to process repos you haven't switched into recently.

## Subcommands

### `cc intel scan [PATH ...]`

Walk the filesystem starting from the given paths (defaults to your CC workspace roots), discover every git repository, and register them for indexing.

```bash
cc intel scan                        # scan default workspace paths
cc intel scan ~/projects ~/oss       # scan specific directories
cc intel scan --max-depth 2          # limit directory traversal depth
```

### `cc intel add-repo PATH [--name NAME]`

Manually register a single git repository.

```bash
cc intel add-repo /home/user/odoo-v19/custom/client-repo
cc intel add-repo ~/oss/mis-builder --name mis-builder
```

### `cc intel list-repos`

Show all registered repositories with their index state, tag counts, and symbol counts.

```bash
cc intel list-repos
cc intel list-repos --json
```

## Related Commands

| Command | Purpose |
|---------|---------|
| `cc reindex` | Walk new commits and extract tags; `--full` reindexes everything; `--dump` prints tag distribution |

The companion web app (`/skills`) consumes the same data — skills graph,
domain breakdown, and symbol search all live there.

## Options

| Flag | Description |
|------|-------------|
| `--json` | Emit raw JSON output |
| `--max-depth N` | Limit scan directory traversal depth (default 4) |
| `--name NAME` | Override the auto-derived repo name (add-repo only) |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `intel.auto_reindex` | `true` | Enable/disable automatic reindex on switch |

## Data Model

| Table | Purpose |
|-------|---------|
| `repository` | Registered git repos — path, origin URL, last indexed SHA/timestamp, enabled flag |
| `skill_tag` | One row per (repo, commit, tag) — weight, raw LOC, committed_at |
| `knowledge_index` | Per-symbol aggregate — commit count, LOC authored, last touched, top files |
