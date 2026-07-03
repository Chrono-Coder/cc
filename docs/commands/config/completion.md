# cc config completion

Print a native shell completion script for `zsh`, `bash`, or `fish`. You normally
don't run this directly — `cc config shell install` writes it into your shell
integration so completion is live automatically. Use it to inspect or regenerate the
script.

## Usage

```bash
cc config completion [zsh|bash|fish]
```

## Arguments

| Argument | Description |
|----------|-------------|
| `shell` | One of `zsh`, `bash`, `fish`. Omit to auto-detect the current shell. |

## What you get

Tab-completion for every cc command, group, verb, and flag, plus context-aware values:

- `cc switch <TAB>` → project names
- `cc cd <TAB>` / `cc sh <TAB>` → environment names
- `cc db use <TAB>` → databases currently in Postgres
- `cc config venv -v <TAB>` → versions
- `cc config theme <TAB>` → theme names; `cc config shell <TAB>` → `install` / `status`

## How it works

The script is **generated from the live CLI** — command list, flags, fixed choices, and
which argument completes to what all come from the parser, so it can never drift.
Dynamic values are read at TAB time straight from cc's SQLite (projects/envs/versions
and the Postgres metadata cache) — no Python process is spawned per keystroke, so it's
instant.

## Manual install

[`cc config shell install`](shell.md) does this for you. To wire it up by hand:

```bash
cc config completion zsh > ~/.cc-cli/shell/cc.completion.zsh
echo 'source ~/.cc-cli/shell/cc.completion.zsh' >> ~/.zshrc
```

(bash: source from `~/.bashrc`; fish: from `~/.config/fish/config.fish`.)

## Related

- [`cc config shell`](shell.md) — installs the integration, including this completion
