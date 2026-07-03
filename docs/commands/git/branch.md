# cc git branch

Update the branch associated with an environment. Prompts you to choose from local and remote branches of the project's git repository, and saves the selection along with the GitHub URL.

## Usage

```bash
cc git branch [PROJECT] [flags]
```

If no project is specified, uses the currently active project.

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project name (tab-completable). If omitted, uses the active project. |

## Flags

| Flag | Description |
|------|-------------|
| `-c`, `--checkout` | Also check out the branch in the working directory after updating the record |

## Examples

```bash
cc git branch
# → Prompts to select environment and branch for the active project

cc git branch acme
# → Prompts to select environment and branch for the acme project

cc git branch -c
# → Updates the branch record AND checks out the branch in git

cc git branch acme -c
# → Same as above, for the acme project
```

After selection, cc saves the branch name and GitHub URL to the environment record. Without `-c`, only the record is updated. With `-c` — or when you run it against the environment that's active in the current directory — the branch is also checked out in the project's working directory.

The branch is always checked out automatically on `cc switch`, regardless of whether `-c` was used.

## Related

- [`cc switch`](../switch.md) — checks out the configured branch on switch
- [`cc git`](README.md) — git & GitHub helpers
