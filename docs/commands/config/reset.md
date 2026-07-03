# cc config reset

Deletes all cc data from the internal database. This drops every cc table — projects,
environments, versions, databases, modules, app state, switch logs, and settings.

## Usage

```bash
cc config reset
```

cc asks for confirmation before proceeding.

> This is irreversible. Your Odoo installations and PostgreSQL databases are not
> affected — only cc's internal SQLite records (`~/.cc-cli/cc_cli.db`) are deleted.

## Related

- [`cc setup`](../setup.md) — re-configure cc after a reset
- [`cc config`](README.md) — settings picker and other config verbs
