# cc cd

Change directory to an environment's project path.

## Usage

```bash
cc cd [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Environment name to cd into directly. |

## Flags

| Flag | Description |
|------|-------------|
| `-c`, `--cwd` | cd to the active environment for the current working directory |

## Behavior

- **No args** — navigates to the active environment (the one you last switched to).
- **`cc cd <name>`** — navigates to the named environment's project path. If the name exists in more than one project, a picker disambiguates.
- **`cc cd --cwd`** — navigates to the active environment tied to your current working directory.

## Workspaces and Multi-Version

In multi-version mode, CC tracks a separate active environment per version/workspace. `cc cd` (no args) shows all active environments across workspaces so you can jump between them. The `--cwd` flag resolves which workspace you're in based on your current directory (matching against version paths).

## Examples

```bash
cc cd              # pick from active envs across all workspaces
cc cd acme_v18     # go directly to acme_v18's project path
cc cd --cwd        # go to the active env for the current version dir
```
