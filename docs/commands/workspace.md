# cc workspace

Manage workspaces — groups of projects sharing an Odoo version.

## Usage

```bash
cc workspace [ACTION] [NAME] [flags]
```

## Actions

| Action | Description |
|--------|-------------|
| `list` | Show all workspaces (default when no action given) |
| `add` | Register an existing directory as a workspace |
| `create` | Build a **new R&D workspace from git worktrees** of an existing version's clones (see below) |
| `consolidate` | Fold duplicate full clones of the same repo into worktrees of one canonical clone, reclaiming disk |
| `edit` | Edit an existing workspace (name, path, R&D, remotes) |
| `open` | Open the workspace's version root in VS Code |
| `assign` | Assign a project to a workspace |
| `remove` | Delete a workspace |

> **Path prompts** (workspace path, version path) accept Tab-completion, `~`/`$VAR`
> expansion, and validate that the directory exists before accepting it (as of 3.8).
>
> The web companion's `/workspaces` page can **edit and delete** workspaces and shows
> each version's venv read-only; building/consolidating worktrees stays CLI-only.

## Flags

| Flag | Description |
|------|-------------|
| `-n`, `--new` | Open in a new VS Code window (with `open`) |

## What is a Workspace?

A workspace groups projects under a single Odoo version. It provides:

- **Version binding** — all projects in the workspace share the same Odoo version root
- **R&D branch checkout** — workspaces with `is_rnd` enabled automatically checkout the environment's branch in shared Odoo repos (odoo, enterprise, design-themes, upgrade-util) on switch
- **Fork remote** — R&D workspaces can define a fork remote for rebasing

## Auto-Creation

`cc setup` automatically creates one workspace per registered version during the wizard. You don't need to create them manually unless you want multiple workspaces on the same version (e.g. one standard, one R&D).

## Worktree workspaces (R&D)

Rather than cloning Odoo once per version, `cc workspace create` and `consolidate` use **git worktrees** so multiple working areas share one object store:

- **`cc workspace create [name]`** — builds a new R&D workspace by adding a `git worktree` of each shared repo (odoo, enterprise, design-themes, upgrade, upgrade-util) from an existing version's clones. A second working area for parallel ticket work costs ~nothing on disk. Creates the directory (detached at the base branch — `cc switch` moves each repo onto the ticket branch) plus its own `version` and `workspace` rows.
- **`cc workspace consolidate`** — folds duplicate *full* clones of the same repo (the "I cloned odoo per version" situation) into worktrees of one canonical clone. **Reversible and safe:** only clean clones are touched, every branch is copied into the canonical first (divergent ones preserved under a `__cc` suffix), and the old clone is *moved* to `<path>.cc-bak` (not deleted). Reclaim disk by removing the `.cc-bak` dirs once you're satisfied.

## R&D Mode

When a workspace has `is_rnd = true`:

1. On `cc switch`, CC checks out the environment's branch in all shared repos
2. Fetches from the fork remote
3. Rebases on the upstream version branch
4. Falls back to the upstream branch when the env branch doesn't exist
5. Rebase conflicts are auto-aborted with a warning

Configure with `cc workspace edit <name>` and set the R&D flag, fork remote, and upstream remote.

## Examples

```bash
cc workspace
# → Lists all workspaces with version, path, R&D flag

cc workspace add
# → Interactive: name, version, path, R&D flag

cc workspace create feature-x
# → Build a new R&D workspace as git worktrees of an existing version's repos

cc workspace consolidate
# → Reclaim disk: fold duplicate full clones into worktrees of one canonical clone

cc workspace open 19
# → Opens VS Code at the v19 workspace root

cc workspace assign myproject
# → Assign a project to a workspace (interactive picker)

cc workspace edit 19
# → Edit workspace settings (name, R&D, remotes)

cc workspace remove old_ws
# → Delete a workspace
```

## Related

- `cc project create --workspace` — create a project directly assigned to a workspace
- `cc switch` — respects workspace R&D settings during branch checkout
