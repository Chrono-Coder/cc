# IDE Writers

CC's "switch and your editor follows" workflow is implemented through a small plugin system. Built-in writers cover VSCode and Cursor; anything else is a third-party plugin.

## Why a plugin system

Historically every editor cc supported needed a dedicated code path inside `cc switch`. That meant new editors required patching `switch_command.py`, and every editor's quirks lived next to every other editor's quirks. It also locked cc to whichever editors the maintainers personally used.

The plugin system separates that out:

- **CC core** computes the new state on every switch (env, db, branch, modules, addons paths, Python interpreter, ports)
- **Writers** project that state into whatever files the editor needs

CC ships VSCode + Cursor writers because those are what the maintainers use. PyCharm, vim, Zed, Helix, Sublime — anyone can add support as a plugin without touching cc itself.

## The contract

An `IdeWriter` is a Python class with four methods:

```python
from pathlib import Path
from cc.ide import IdeWriter, CcState

class MyEditorWriter(IdeWriter):
    name = "my-editor"

    def detect(self, workspace_path: Path) -> bool:
        """Return True if this editor is in use in the given workspace."""
        return (workspace_path / ".my-editor").is_dir()

    def setup(self, workspace_path: Path) -> None:
        """Write one-time artifacts (debugger templates, run configs)."""
        ...

    def apply(self, workspace_path: Path, state: CcState) -> None:
        """Project per-switch dynamic state into the editor's config."""
        ...
```

That's the entire interface.

## Setup vs Apply — the load-bearing distinction

The two methods are called at different times for different reasons:

| | `setup()` | `apply()` |
|---|---|---|
| **When** | Once per workspace (`cc config ide setup`, `cc workspace add`) | Every `cc switch` |
| **What it writes** | Templates that reference state through indirection (e.g. VSCode's `launch.json` with `${config:cc.*}` keys) | Per-switch dynamic values (e.g. VSCode's `settings.json`: db name, addons, modules, Python interpreter) |
| **Idempotent?** | Yes | Yes |
| **Survives switches?** | Yes — never re-written on switch | Overwritten on each switch (but merge-safe — unrelated keys preserved) |

**`cc switch` MUST NOT touch `launch.json` (or any other template file)** — that's contracted behavior, asserted by a regression test. Users edit launch.json all the time; cc respects that.

## CcState — the data contract

What writers receive every switch:

```python
@dataclass(frozen=True)
class CcState:
    workspace_path: str    # where the editor's config dir lives
    env_name: str
    project_name: str
    version_name: str      # "17.0" etc.
    branch: str
    db: str
    odoo_bin: str
    port: str
    addons_path: str
    modules: str           # comma-separated module names
    upgrade_path: str
    python_path: str
```

Empty strings mean "unset" — writers should treat empty fields as "do not write this key" rather than writing `""`. New fields may be added in future minor versions, but existing fields will never be removed or renamed.

## Discovery

CC looks for writers in three places, in order:

1. **Built-in** — `cc.ide.vscode.VSCodeWriter`, `cc.ide.vscode.CursorWriter`
2. **Entry-point plugins** — packages that register under the `cc.ide_writers` group:

   ```toml
   # pyproject.toml of your plugin package
   [project.entry-points."cc.ide_writers"]
   sublime = "cc_sublime_writer:SublimeWriter"
   ```

3. **Local drop-in** — any `.py` file in `~/.cc-cli/ide_writers/` that defines an `IdeWriter` subclass

If multiple sources register the same `name`, later sources win — a local drop-in can override a built-in.

## Selection

Which writers run on a given switch is controlled by the `cc.ide` setting:

| Value | Behavior |
|---|---|
| `auto` (default) | Run every writer whose `detect()` returns True |
| `none` | Skip all writers — useful for headless / terminal-only setups |
| `vscode` | Force-enable the VSCode writer (skip detection) |
| `cursor` | Force-enable the Cursor writer |
| `code` | Legacy alias — maps to `vscode` (so existing users with `ide=code` keep working) |
| `vscode,my-plugin` | Comma-separated — enable specific writers in order |

Change it from the UI via `cc config`, or directly:

```bash
cc ide list                # see which writers are registered and which are active
cc config ide setup            # write templates for the active version's path
```

## Writing your own — minimal example

A writer that drops a single Odoo run config into `.idea/runConfigurations/`:

```python
# ~/.cc-cli/ide_writers/pycharm.py
from pathlib import Path
from cc.ide import IdeWriter, CcState

TEMPLATE = """\
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="Odoo (cc)" type="PythonConfigurationType" factoryName="Python">
    <module name="$WORKSPACE$" />
    <option name="SCRIPT_NAME" value="$ODOO_BIN$" />
    <option name="PARAMETERS" value="--addons-path=$ADDONS$ -d $DB$ -p $PORT$" />
    <option name="SDK_HOME" value="$PYTHON$" />
  </configuration>
</component>
"""

class PycharmWriter(IdeWriter):
    name = "pycharm"

    def detect(self, workspace_path: Path) -> bool:
        return (workspace_path / ".idea").is_dir()

    def setup(self, workspace_path: Path) -> None:
        # PyCharm regenerates run configs from XML on disk; setup is a no-op.
        pass

    def apply(self, workspace_path: Path, state: CcState) -> None:
        out = workspace_path / ".idea" / "runConfigurations"
        out.mkdir(parents=True, exist_ok=True)
        content = (TEMPLATE
            .replace("$WORKSPACE$", state.workspace_path)
            .replace("$ODOO_BIN$", state.odoo_bin)
            .replace("$ADDONS$", state.addons_path)
            .replace("$DB$", state.db)
            .replace("$PORT$", state.port)
            .replace("$PYTHON$", state.python_path)
        )
        (out / "Odoo_cc.xml").write_text(content)
```

Drop that file into `~/.cc-cli/ide_writers/`, set `cc.ide = pycharm` (or leave on `auto` if you have `.idea/`), and `cc switch` will keep PyCharm's run config in sync.

## See also

- [`cc ide`](../commands/config/ide.md) — command reference
- [`cc switch`](../commands/switch.md) — what triggers `apply()`
- Source: [`src/cc/ide/`](https://github.com/Chrono-Coder/cc/tree/main/src/cc/ide) — `VSCodeWriter` is the reference implementation
