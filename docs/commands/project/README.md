# cc project

Manage projects and their environments. A **project** is the container — a client
or codebase (e.g. `acme`, `globex`); an **environment** is one working
configuration of that project (its path, version, branch, database, and modules).
Because environments and modules belong to a project, they live as verbs under
`cc project`.

## Usage

```bash
cc project <verb> [args]
```

Bare `cc project list` is the default — `cc project` with no verb prints help.

## Verbs

| Verb | Description |
|------|-------------|
| [`cc project create`](create.md) | Create a project |
| [`cc project list`](list.md) | List projects |
| [`cc project delete`](delete.md) | Delete a project and all its environments |
| [`cc project keep`](keep.md) | Exempt a project from auto-archiving (toggle) |
| [`cc project env`](env.md) | Manage a project's environments (create, list, delete, edit, archive, pin, …) |
| [`cc project cloc`](cloc.md) | Count lines of code across the project's modules |
| [`cc project module`](module.md) | Update the active environment's module list and launch mode |
| [`cc project open`](open.md) | Open a project in your IDE without switching |

## Related

- [`cc switch`](../switch.md) — switch the active environment (creates the project if it doesn't exist)
- [`cc db`](../db/README.md) — manage an environment's databases
- [Projects & Environments](../../concepts/projects-environments.md) — the data model
- [Command Reference](../README.md)
