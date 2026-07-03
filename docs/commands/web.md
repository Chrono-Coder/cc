# cc web

Start the CC Companion App — a local Next.js web dashboard that reads directly from `~/.cc-cli/cc_cli.db`.

## Usage

```bash
cc web
cc web --port 4000
cc web --no-browser
```

## Flags

| Flag | Description |
|------|-------------|
| `-p`, `--port PORT` | Port to run the app on (default: 3000) |
| `--no-browser` | Start without opening the browser automatically |

## Security

The companion binds to `127.0.0.1` only and requires a local auth token. `cc web`
generates the token once (stored at `~/.cc-cli/web.token`, mode 600) and opens the
browser with `?token=...`, which the app exchanges for a session cookie. With
`--no-browser`, the full URL including the token is printed so you can open it
yourself. Requests without the token, with a non-local `Host`, or cross-origin
mutations are rejected.

## Pages

| Page | Description |
| ---- | ----------- |
| **Home** (`/`) | Active environments at a glance + GitHub code reviews (needs review / your open PRs) |
| **Projects** (`/projects`) | All projects and environments sorted by last used, with search |
| **Environment** (`/env/[id]`) | Full detail for a single environment — links, modules, LOC, live active badge |
| **Timesheet** (`/timesheet`) | Bar chart and pie chart of time per project; 7d/14d/30d/90d range selector |
| **History** (`/history`) | Switch timeline grouped by day with durations; delete individual entries |
| **Versions** (`/versions`) | All configured Odoo versions with branch, port, path, and last-fetched time |
| **Health** (`/health`) | Data quality checks across projects and environments |
| **Settings** (`/settings`) | GitHub PAT + username for code reviews; Odoo SH session cookie for SH sync |

## Environment detail page

Click any environment name in a project card to open `/env/[id]`, which shows:

- Version, branch (colored pill), database (colored pill)
- Quick-open button for `localhost:PORT/web`
- Links to GitHub (goes directly to the branch), Odoo SH, and Odoo ticket (extracted from branch name)
- Module list with **Lines of Code** — scanned automatically on page load by walking the `project_path` filesystem
- Live active badge — polls every 5 seconds, updates without a page refresh

## Health checks

The `/health` page surfaces data-quality issues across projects and environments:

- Projects with no environments
- Environments missing a branch, version, database, or GitHub URL
- Projects without an SH URL
- Stale environments (unused 90+ days)
- Duplicate environment names

The **Health** sidebar link shows a badge with the total issue count.

## Settings — GitHub integration

Add a GitHub **classic PAT** (with `repo` scope) and your GitHub username to enable the Code Reviews section on the home dashboard. Fine-grained PATs require org owner approval for private repos — classic PATs work without it.

## Settings — Odoo SH sync

Paste your Odoo SH session cookie (`session_id`) from browser DevTools. Click **Sync Now** to scrape `odoo.sh/project`, match projects to CC via GitHub URL, and write `sh_url` back to each project automatically.

## Requirements

Node.js must be installed. The companion app lives in the `web/` directory of the CC repo.

## Related

- `cc sh` — open an Odoo SH project in the browser (requires `sh_url` to be set)
