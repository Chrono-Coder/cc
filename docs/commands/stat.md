# cc stat

Show the environments for the active project.

## Usage

```bash
cc stat
```

## Output

Displays a detailed card for each environment in the active project, showing its status, path, version, branch, database, and associated modules.

```
Environments for 'acme':
╭────────────────────────────────────────────────────────────╮
│ 🚀 Environment: acme / acme_approvals       🟢 ACTIVE      │
├────────────────────────────────────────────────────────────┤
│ 📁 Path       │ /home/odoo/odoo-v19/custom/acme
│ 🧩 Version    │ v19
│ 🌐 GitHub     │ https://github.com/your-org/acme
│ 🌿 Branch     │ 19.0-feature-approvals
│ 🗄️  Database  │ acme_approvals
├────────────────────────────────────────────────────────────┤
│ 📦 Modules
│   • acme_approvals
╰────────────────────────────────────────────────────────────╯
```

🟢 **ACTIVE** means this is the active environment — the one you last switched to (or, with [multi-version mode](../concepts/multi-version-mode.md) on, the active env for the current version). 🟡 **INACTIVE** means the environment exists but isn't the active one.

## Notes

`cc stat` is scoped to the active project. To see environments for a different project use `cc env list <project>`.
