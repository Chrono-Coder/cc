# cc reindex

Walk new commits in registered repositories, run language packs, and update skill tags + knowledge index.

## Usage

```bash
cc reindex                          # index all enabled repositories (incremental)
cc reindex --repo client-repo       # index only one repo
cc reindex --full                   # rebuild from scratch (ignore incremental state)
cc reindex --dump client-repo       # print raw tag distribution + top symbols
```

## How it works

The indexer walks `git log --all --remotes --no-merges --author=$me` for each repository, streams the diff, and runs every applicable language pack over each commit. Results are written to the `skill_tag` and `knowledge_index` tables.

Indexing is **incremental** — commits already indexed (by SHA) are skipped. First run on a 3-year repo typically completes in 1-3 seconds.

Lock files, generated translations, minified bundles, and vendored code are excluded via git pathspec — they don't represent authored work.

## Options

| Flag | Description |
|------|-------------|
| `--repo NAME` | Limit to one repo (by name or id) |
| `--full` | Re-process all commits, ignoring incremental state |
| `--dump REPO` | Print raw SkillTag rows for the given repo (validation) |
| `--limit N` | `--dump` only: how many recent rows to show (default 50) |
| `--json` | Emit raw JSON output |

## Language Packs

Two built-in packs run automatically based on project detection:

**Python Generic** — fires on any repo with `.py` files:
`test`, `external_api`, `cli`, `db_query`, `async_io`, `concurrency`, `dataclass`, `regex_heavy`, `security`, `config_ipc`

**Odoo** — fires on repos with a valid `__manifest__.py` + sibling model/view directories:
- Skill tags: `model_definition`, `model_override`, `wizard`, `compute_method`, `constraint`, `controller`, `report`, `performance`, `security`, `cron_or_queue`, `migration`
- Asset tags: `assets_backend`, `assets_frontend`, `assets_pos`, `assets_qweb`
- Frontend tags: `owl_component`, `js_widget`, `owl_template`, `style`, `js_test`, `tour_test`, `website`
- Business domains: `domain_hr`, `domain_accounting`, `domain_inventory`, `domain_mrp`, `domain_sales`, `domain_crm`, `domain_pos`, `domain_website`, and 14 more — each with subdomains (e.g. `domain_hr_payroll`, `domain_accounting_assets`)
