# cc git

Git & GitHub helpers — set an environment's branch, fetch the Odoo repos, open the
repo page, and drive the pull request workflow. `cc git pr` wraps the
[`gh` CLI](https://cli.github.com/), so PR operations need `gh` installed and
`gh auth login` completed.

## Usage

```bash
cc git <verb> [args]
```

## Verbs

| Verb | Description |
|------|-------------|
| [`cc git branch`](branch.md) | Pick and save an environment's branch (and optionally check it out) |
| [`cc git fetch`](fetch.md) | Fetch the active version's Odoo repos (R&D-aware), or `--all` versions |
| [`cc git github`](github.md) | Open the project's GitHub page in the browser |
| [`cc git pr`](pr.md) | Pull request workflow — list, create, view, merge, checkout, checks (wraps `gh`) |

## Related

- [`cc switch`](../switch.md) — checks out the configured branch on switch
- [Command Reference](../README.md)
