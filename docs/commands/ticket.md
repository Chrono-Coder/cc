# cc ticket

Open the Odoo task linked to an environment in the browser.

## Usage

```bash
cc ticket [name]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project name (tab-completable). If omitted, uses the **active** environment. |

## Examples

```bash
cc ticket              # open the active environment's ticket
cc ticket acme         # pick an env in 'acme', open its ticket
```

## How It Works

CC resolves the ticket in two steps:

1. **`ticket_ids` field** — if the environment has ticket IDs set (edit them with
   `cc env edit` or in the companion), cc uses those. With more than one, it asks
   which to open.
2. **Branch fallback** — otherwise it extracts a numeric ID from the branch name,
   following the Odoo convention:

   ```
   19.0-1234567-approvals-pjhe
         ^^^^^^^
         ticket ID → opens odoo.com/odoo/project.task/1234567
   ```

   Works with both `17.0-XXXXXX-...` and plain `XXXXXX-...` branch names.
