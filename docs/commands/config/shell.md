# cc config shell

Manage cc's shell integration — the `cc` function, daemon auto-start, prompt-segment
helper, and tab-completion that get written to your rc file.

## Usage

```bash
cc config shell                          # status (default)
cc config shell status                   # check whether integration is installed
cc config shell install                  # install/reinstall for current shell
cc config shell install --shell fish     # force fish even if zsh is detected
cc config shell install --force          # reinstall when already installed
```

## Arguments

| Argument | Description |
|----------|-------------|
| `action` | `status` (default) or `install` |

## Flags

| Flag | Description |
|------|-------------|
| `--shell {zsh\|bash\|fish}` | Force a specific shell (auto-detected from parent process / `$SHELL` otherwise) |
| `-f`, `--force` | Reinstall even when integration is already in place |

## Actions

| Action | Description |
|---|---|
| `status` (default) | Print whether integration is installed for the detected shell |
| `install` | Write the integration file + append source line to your rc file |

## What it installs

Writes a small shell file (`~/.cc-cli/shell/cc.zsh`, `cc.bash`, or `cc.fish`) that defines:

1. **`cc` shell function** — wraps the CLI with a `CC_RUN_FILE` env var. Lets `cc switch` / `cc cd` / switch hooks change your shell's working directory and activate pyenv venvs by writing shell commands that get `source`d in the parent shell.
2. **Daemon auto-start** — silently starts `cc daemon` if the socket isn't already up.
3. **Prompt helper** — a powerlevel10k segment (`cc_env`) / bash-fish equivalent (`__cc_env_segment`) showing the active environment name, read directly from `~/.cc-cli/cc_cli.db` for zero latency.
4. **Tab-completion** — a native completion script (see [`cc config completion`](completion.md)) generated from the live CLI, with values pulled from SQLite at TAB time. This is what makes `cc <TAB>` work.

Then appends a `source ~/.cc-cli/shell/cc.zsh` line (or bash/fish equivalent) to your `~/.zshrc` / `~/.bashrc` / `~/.config/fish/config.fish`.

## After install

```bash
source ~/.zshrc                   # or source ~/.config/fish/config.fish
```

To pick up the function in the current terminal. New terminals get it automatically.

For zsh + powerlevel10k users, add `cc_env` to `POWERLEVEL9K_RIGHT_PROMPT_ELEMENTS` in
`~/.p10k.zsh`. For bash add `$(__cc_env_segment)` to your `PS1`; for fish add
`__cc_env_segment` to your `fish_right_prompt`.

## When to use this manually

`cc setup` installs shell integration automatically on first run. Use `cc config shell install` standalone when:

- Your dotfiles got reset and the source line is gone
- You switched from zsh to fish (or vice versa)
- The `cc` function stopped working and you want to reinstall fresh

## Related

- [`cc config completion`](completion.md) — the completion script this installs
- [`cc setup`](../setup.md) — first-time wizard (includes shell integration as a step)
- [`cc daemon`](../daemon/README.md) — daemon lifecycle (auto-start lives in the shell integration)
