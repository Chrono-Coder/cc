# cc git github

Open a project's GitHub page in the browser.

## Usage

```bash
cc git github [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project name (tab-completable). If omitted, uses the active project. |

## Flags

| Flag | Description |
|------|-------------|
| `-p`, `--path` | Use the current working directory instead of the active project |

## Examples

```bash
cc git github              # open active project's GitHub, on the active branch
cc git github acme         # open acme's GitHub page (prompts for environment)
cc git github -p           # open GitHub for the repo at current path
```

## How It Works

- **Active project:** opens the active environment's stored GitHub URL on its branch — `github.com/org/repo/tree/branch`.
- **With a project name:** prompts for an environment, then opens that environment's path's GitHub repo page.
- **With `-p` or no active project:** reads the git remote (`origin`) from the current directory and opens the repo page.

## Related

- [`cc git`](README.md) — git & GitHub helpers
- [`cc git pr`](pr.md) — pull request workflow
