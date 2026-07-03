# cc git pr

GitHub pull request workflow — list, create, view, merge, checkout, and check PRs.

Requires the [`gh` CLI](https://cli.github.com/) with `gh auth login` completed.

## Usage

```bash
cc git pr                    # interactive TUI picker of your open PRs
cc git pr list               # same as bare `cc git pr`
cc git pr create [base]      # open a compare URL: current branch → base
cc git pr view [number]      # show PR details
cc git pr merge [number]     # merge a PR
cc git pr checkout [number]  # checkout PR branch locally
cc git pr checks [number]    # show CI status checks
```

`view`, `merge`, `checkout`, and `checks` take a PR number — **or omit it** and cc
resolves the open PR for your **current branch** (via `gh pr list --head`).

## Arguments

| Argument | Description |
|----------|-------------|
| `action` | One of `list`, `create`, `view`, `merge`, `checkout`, `checks`. Defaults to the interactive list. |
| `target` | A PR number (for `view`/`merge`/`checkout`/`checks`) or a base branch (for `create`). |

## Actions

### list (default)

Fetches your open PRs via `gh search prs --author @me` and shows them in a TUI picker:

| Key | Action |
|-----|--------|
| `↑` / `↓` | navigate |
| `Enter` / `o` | open the PR in your browser |
| `c` | check the PR branch out locally |
| `m` | merge the PR (prompts for method) |
| `esc` | cancel |

### create

Opens a GitHub **compare URL** for `current branch → base` in your browser (it
does not create via the CLI). The base defaults to the **active version's
branch** (e.g. `18.0`), since Odoo PRs target the version line, not `main`. Pass
a base explicitly to override:

```bash
cc git pr create            # base = active version's branch
cc git pr create 19.0       # base = 19.0
cc git pr create main       # base = main
```

### view

Shows PR details: title, state, review decision, branch, author, diff stats, and URL.

### merge

Merges a PR. Prompts for merge method (squash, merge, or rebase).

### checkout

Checks out the PR branch locally via `gh pr checkout`.

### checks

Shows CI commit statuses for the PR's head branch.

## Flags

| Flag | Description |
|------|-------------|
| `--json` | Output open PRs as JSON (with `list` or the default action) |

## Examples

```bash
cc git pr                    # pick an open PR (open / checkout / merge from the picker)
cc git pr --json             # JSON output
cc git pr create 19.0        # compare URL: current branch → 19.0
cc git pr view               # details for the current branch's PR
cc git pr merge              # merge the current branch's PR
cc git pr checkout 38        # checkout PR #38 branch
cc git pr checks             # CI checks for the current branch's PR
```

## Related

- [`cc git github`](github.md) — open the GitHub repo page
- [`cc git branch`](branch.md) — update the branch on an environment
- [`cc git`](README.md) — git & GitHub helpers
