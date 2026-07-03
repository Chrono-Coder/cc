# cc project cloc

Count lines of code across modules in a project using Odoo's built-in `cloc`
tool.

## Usage

```bash
cc project cloc [name] [flags]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `name` | Project to scan. Omit to scan the active project. |

## Flags

| Flag | Description |
|------|-------------|
| `-a`, `--active` | Count only the environment's active modules (skip the picker) |

Without `-a`, cc opens an interactive checkbox picker of every module in the
project. Use the fuzzy filter to narrow it down, Space to toggle, Enter to
confirm. Selecting **Select all** scans every module.

## Examples

```bash
cc project cloc           # pick modules in the active project
cc project cloc acme      # pick modules in project 'acme'
cc project cloc -a        # scan the active environment's active modules
```

```
CLOC Report (2 modules)
───────────────────────────────────────────────────────────────
Module                                               Code Lines
───────────────────────────────────────────────────────────────
acme_approvals                                              269
acme_base                                                   142
───────────────────────────────────────────────────────────────
TOTAL                                                       411
───────────────────────────────────────────────────────────────
```

## Related

- [`cc project module`](module.md) — set which modules are active on an environment
- [`cc project env`](env.md) — manage environments
- [Command Reference](../README.md)
