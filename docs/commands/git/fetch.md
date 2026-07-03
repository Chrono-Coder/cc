# cc git fetch

Fetch the latest changes for the active version's Odoo repositories (`odoo`, `enterprise`, `design-themes`), or every configured version with `--all`. Repos are fetched concurrently.

The fetch is **R&D-aware**:

- **Source checkouts** (non-R&D workspaces) are never hand-edited, so cc runs `git fetch`, `git restore .`, and `git pull -f` to keep them pristine and current (`fetch + pull` mode).
- **R&D workspaces** hold your uncommitted work, so cc runs `git fetch` **only** — it never restores or pulls there, so nothing you haven't committed is ever discarded (`fetch-only` mode).

## Usage

```bash
cc git fetch
cc git fetch --all
```

## Flags

| Flag | Description |
|------|-------------|
| `-a`, `--all` | Fetch all configured versions, not just the active one |

## Examples

```bash
cc git fetch
# → Fetches the active version's repos

cc git fetch --all
# → Fetches all configured Odoo versions
```

## Related

- [`cc switch`](../switch.md) — triggers a background auto-fetch on switch if auto-fetch is enabled and the interval has elapsed
- [`cc config`](../config/README.md) — pick "Auto-fetch interval (hours)" from the settings picker
- [`cc git`](README.md) — git & GitHub helpers
