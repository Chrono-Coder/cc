# cc rnd

R&D workflow for developers who work across the shared Odoo repos (odoo, enterprise, upgrade). Instead of a full clone per version, `cc rnd` builds workspaces out of **git worktrees** of one canonical clone, so branches are cheap to spin up and switch between.

## Subcommands

```bash
cc rnd create <name>          # new R&D workspace by git-worktreeing a version's repos
cc rnd consolidate            # fold duplicate full clones into worktrees of one canonical clone
cc rnd project <name>         # create an R&D project in a worktree workspace
cc rnd fw <name>              # add any missing forward-port envs for an R&D project
```

### cc rnd create

Creates an R&D workspace by worktreeing the repos of an Odoo version, rather than re-cloning them.

```bash
cc rnd create 18-experiments
```

### cc rnd consolidate

Reversible dedup: finds duplicate full clones on disk and folds them into worktrees of a single canonical clone, reclaiming space without losing any branch.

### cc rnd project

Creates a project inside a worktree workspace and auto-discovers its forward-port branches.

```bash
cc rnd project my-fix                 # uses the workspace for the current directory
cc rnd project my-fix -w 18-experiments
```

### cc rnd fw

Scans the fork and adds any missing forward-port environments (`{target}-{main}-fw` chains) for an existing R&D project.

```bash
cc rnd fw my-fix
```

## Switch-rebase

In an R&D workspace, `cc switch` checks out and rebases the environment's branch across the shared repos. This is controlled by the **`rnd.auto_rebase`** setting (default on) — turn it off in `cc config` to switch without cc touching git.

## Related

- [`cc switch`](switch.md) — the switch-rebase happens here
- [`cc workspace`](workspace.md) — non-R&D workspaces
- [Settings](../configuration/settings.md) — `rnd.auto_rebase`
