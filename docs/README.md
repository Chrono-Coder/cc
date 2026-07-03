# CC — Odoo Dev CLI

CC is a command-line tool built for Odoo developers who work across multiple projects, versions, and environments every day.

Instead of manually switching databases, checking out branches, updating launch configs, and tracking what you worked on — CC does it in one command.

```bash
cc switch acme
```

That's it. Project switched, IDE configured, branch checked out, timesheet logged.

<!-- 📸 IMAGE: Short GIF of cc switch in action — terminal showing the environment selector, then IDE opening -->

---

## What CC Does

- **Instant project switching** — one command switches your active project, checks out the right branch, and updates your VS Code / Cursor launch config
- **Multi-version support** — register and switch across v17, v18, and v19 projects, each with its own workspace, port, and branch
- **Timesheet** — automatically tracks time spent per project on every switch, plus explicit manual entries you start/end with notes; edit anything that's off, flag long sessions, punch out
- **Environment management** — multiple environments per project (different branches, databases, module sets)
- **Auto-updates** — notifies you when a new version of CC is available

---

## Who It's For

Odoo developers who:
- Work on multiple client projects in parallel
- Use multiple Odoo versions (v16, v17, v18, v19...)
- Are tired of manually managing launch.json, git checkouts, and database switches
- Want a lightweight timesheet without a separate tool

→ [Installation guide](getting-started/installation.md)
→ [Your first switch](getting-started/first-switch.md)
