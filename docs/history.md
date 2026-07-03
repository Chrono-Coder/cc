# History

The story of cc — from a folder of shell scripts to a daemon-backed CLI with encrypted multi-device sync.

## Timeline

### Sep 2024 — First commit

Two Odoo developers (Peter-John Hein and Yousef Al Nashef) tired of manually juggling project directories, database names, and module lists across dozens of Odoo environments. The `chronofeldyx` org repo goes up with a Python argument parser and a command skeleton.

### Nov–Dec 2024 — Core commands

The foundational CLI takes shape: `cc switch` to change projects, `cc config` to set up Odoo versions, `cc initdb` to initialize databases from dump files. A unified fuzzy directory search lets cc find project folders by partial name across all Odoo version roots. `cc ticket`, `cc github`, and `cc sh` add quick-open shortcuts to external tools.

### Jan 2025 — Database management

`cc copy` and `cc restore` add PostgreSQL dump/restore workflows. Database expiration date handling for Odoo demo instances.

### Feb 2025 — The daddy shell experiment

A persistent Python shell wrapping cc — the idea was to keep state between commands. It worked but added complexity without enough benefit. Would be removed in v2.0.

### Mar 2025 — Feature sprint and v1.0

Rapid development: `cc module` (install/upgrade Odoo modules), `cc fetch` (update all Odoo repos), `cc cd` (navigate to project directory), `cc db` (switch databases), `cc cloc` (count lines of code), `cc project` (manage projects), argcomplete for tab completion, and a VSCode extension for IDE integration.

**v1.0.0 released March 16, 2025.** A working CLI tool — Python-based but still using `storage.json` for persistence and questionary for prompts.

### May–Oct 2025 — Quiet evolution

Environments become a first-class concept. The ORM gains one-to-many relations. SQLite starts replacing the JSON config file. A period of using the tool daily and understanding what needs to change for the next leap.

### Feb 2026 — v2.0: The rewrite

A ground-up rebuild. The daddy shell is killed. cc becomes pip-installable. SQLite fully replaces `storage.json`. The custom prompt_toolkit prompter replaces questionary with rounded frames and themed selectors. Data moves to `~/.cc-cli/`. Not backwards compatible — a clean break from v1.

### Mar 2026 — The explosive month

Three major versions ship in four weeks:

**v2.1** adds multi-version active mode (track one project per Odoo version), timesheet telemetry (`cc time`), pyenv virtualenv integration, single-repo mode (one directory with branch checkouts), auto-fetch on switch, `cc cloc`, and an update notifier.

**v2.2** launches the **CC Companion** — a Next.js web dashboard reading directly from the SQLite database. Home dashboard with active environments and GitHub reviews, project grid, environment detail pages with CI checks and CLOC, timesheet charts, switch history, health page, `cc doctor` with 9 auto-fix checks, and Odoo SH sync. The sidebar, the logo, the whole UI — built in a week.

**v2.3** migrates the companion to shadcn/ui with Suspense streaming, history pagination, and consolidated utilities.

### Apr 2026 — Polish

**v2.4** adds `cc backup` (named PostgreSQL snapshots), `cc tunnel` (SSH to Odoo.sh databases), CLI color theming (5 palettes), a TipTap WYSIWYG notes editor, ticket IDs as pill badges, a Cmd+K quick-switcher, pin/star environments, collapsible sidebar, and 10 web themes with full light mode support.

### May 2026 — Architecture revolution

**v3.0** introduces the daemon — a long-running background process on a Unix socket (`~/.cc-cli/cc.sock`) with JSON-RPC 2.0. Every write now flows through the daemon (single-writer guarantee). Business logic moves from CLI commands to a typed service layer with `@rpc_method` decorators and router-level validation. Real-time SSE events push state changes to the web companion. Postgres queries get connection pooling and caching. 77 tests.

**v3.0.1** adds pub/sub event bus, pre/post switch hooks (stdout eval'd in the parent shell), daemon auto-start with exponential backoff, and `cc module -i` mode toggle.

**v3.1** brings workspaces (group projects by Odoo version with optional R&D mode), virtual projects (time-tracking only, no filesystem), `cc venv` TUI for pyenv management, database pools per environment, `--json` flag for scripting, and the intel/skill telemetry system — scan git repos, extract skill tags from commits, build a knowledge index per symbol. The web companion gains a skills visualization page. 150 tests.

**v3.2** rewrites every output surface with rich. Themed console singleton, shared table/panel builders, rounded frames on all TUIs. The logger gets rich handlers. 7 themes pruned to 4. The 1200-line config command decomposes into domain modules (shell installer, theme picker, workspace registration, venv linker, config schema). CI workflow added.

**v3.3** ships multi-device sync as an opt-in plugin (`pip install cc-cli[sync]`). A central server (Raspberry Pi behind a Cloudflare Tunnel) receives AES-256-GCM encrypted push/pull cycles over HTTPS. The daemon auto-syncs every 5 minutes. Foreign keys resolve by natural key so each device keeps its own ID space. `cc sync resolve` remaps paths and auto-clones repos on new devices. A `.env` file keeps secrets out of the shell profile and the sync stream. 158 tests.

**v3.4** focuses on public readiness. A new installer creates an isolated venv — no system Python pollution, no pyenv dependency, no reinstalling per Python version. Bash support joins zsh and fish. Every bare `print()` is replaced with themed console output. Every error message tells you what to do next. Spinners on all long operations. TUI selectors clean up properly on exit. `cc` with no args shows a welcome screen. The setup wizard asks where your Odoo installs are instead of scanning your entire home directory. launch.json is merged rather than replaced. The legacy v1 migration command is removed.

### Jun 2026 — GitHub, Postgres, and a grammar for the CLI

**v3.5–v3.7** rebuild the GitHub integration on top of the `gh` CLI — `cc git pr` grows a full pull-request lifecycle (list, create, view, merge, checkout, checks), and env detail pages surface live CI status.

**v3.8** lands a real PostgreSQL subsystem: `cc db` becomes a family — use, list, drop, init, copy, restore, backup, rename, link, extend, check — that works against both a native Postgres and a dockerized one (via `docker exec psql`), with a self-discovering connector. Native shell completion is generated from the CLI parser itself, so it can't drift.

**v3.9** reshapes the whole surface into **noun groups** — `cc db …`, `cc git …`, `cc project …`, `cc config …` — replacing the flat pile of top-level commands with a consistent `cc <group> <verb>` grammar.

### Jun–Jul 2026 — The plugin detour, and the road back

**v3.10** splits the company-specific features — skill telemetry, the R&D workflow, and the web companion — out of core into installable **plugins**, wired through entry-point groups, to keep a public `cc` lean. The machinery was clean, but the seams never fully separated: core kept knowing about its own plugins.

**v3.11** reverses the split. Plugins turn out to be the wrong altitude for a first-party monorepo, so `intel`, `rnd`, and `web` fold back into core and each becomes a **setting** you toggle rather than a package you install. The same release brings the timesheet's manual-span layer, the return of opt-in multi-active environments, and a security-and-portability hardening pass across every surface: a token-authenticated web companion, a locked-down sync server, SQLite-version portability, and configurable (rather than hardcoded) conventions.

### Jul 2026 — v4.0, going public

**v4.0** is the first public release: everything built across the 3.x line, consolidated into one version. One package, one `cc`, features gated by config — installable by anyone with Python and Git.

## By the numbers

| Metric | Count |
|--------|-------|
| First commit | September 20, 2024 |
| First public release | v4.0.0, July 3, 2026 |
| Test count | 378 |
| Syncable tables | 10 |
| CLI command surface | 21 top-level groups + verbs |
| Web companion routes | 12 pages · 31 API routes |
| Contributors | 2 |
