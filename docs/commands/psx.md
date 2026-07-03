# cc psx

Opens the PSX Runbot page for the active (or specified) project's branch in your browser.

## Usage

```bash
cc psx [PROJECT]
```

If no project is specified, uses the branch from the currently active environment.

## Examples

```bash
cc psx
# → Opens the runbot page for the active environment's branch

cc psx acme
# → Prompts to select an environment for acme, then opens its branch on runbot
```

> The environment must have a branch configured. Set one with `cc git branch`.

## Configuration

The URL is built from the **`psx.url_template`** setting, with `{branch}` as the
placeholder (set it in `cc config`). Left blank, it defaults to Odoo's PS runbot.

## Related

- `cc git branch` — configure the branch for an environment
- `cc git pr` — open the GitHub pull request for the active branch
