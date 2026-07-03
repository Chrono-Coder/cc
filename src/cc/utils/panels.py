"""Shared rich Panel/Table builders for cc output."""
from typing import Any

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text


def themed_table(title: str = "", **overrides: Any) -> Table:
    """Pre-configured rich Table for cc output.

    Defaults: rounded box, heading-styled title + header, primary borders,
    left-aligned title, single-cell padding. Pass any kwarg to override
    (e.g. border_style="muted" for less visually dominant tables).

    All cc tables should use this so visual style stays consistent.
    """
    kwargs: dict[str, Any] = {
        "box": box.ROUNDED,
        "title_style": "heading",
        "title_justify": "left",
        "header_style": "heading",
        "border_style": "primary",
        "padding": (0, 1),
    }
    kwargs.update(overrides)
    if title:
        kwargs["title"] = title
    return Table(**kwargs)


def env_card(env: dict[str, Any]) -> Panel:
    """Boxed environment card. Input is a normalized dict with keys:
    name, project_name (optional), project_path, version, github_url,
    branch_name, database, sh_url, modules (list[str]), is_active (bool),
    is_virtual (bool, optional), lifecycle (str, optional: active|merged|archived).
    """
    status = (
        "[success]🟢 ACTIVE[/]"
        if env.get("is_active")
        else "[warning]🟡 INACTIVE[/]"
    )
    # Lifecycle (active|merged|archived) is distinct from the active/inactive
    # switch state above — only badge it when it's not the default "active".
    lifecycle = env.get("lifecycle")
    lifecycle_badge = f"  [muted]({lifecycle})[/]" if lifecycle and lifecycle != "active" else ""
    project_label = (
        f"[muted]{env['project_name']} / [/]"
        if env.get("project_name")
        else ""
    )
    header = Text.from_markup(
        f"🚀 [bold]Environment:[/] {project_label}{env['name']}  {status}{lifecycle_badge}"
    )

    is_virtual = bool(env.get("is_virtual"))

    body = Table.grid(padding=(0, 1))
    body.add_column(width=2)
    body.add_column(style="primary", width=10)
    body.add_column(overflow="fold")
    if not is_virtual:
        body.add_row("📁", "Path", env.get("project_path") or "N/A")
    body.add_row("🧩", "Version", env.get("version") or "N/A")
    if not is_virtual:
        body.add_row("🌐", "GitHub", env.get("github_url") or "N/A")
        body.add_row("🌿", "Branch", env.get("branch_name") or "N/A")
    body.add_row("💾", "Database", env.get("database") or "N/A")
    if env.get("sh_url"):
        body.add_row("🟣", "SH", env["sh_url"])

    parts = [header, Rule(style="primary"), body]

    if not is_virtual:
        modules = Table.grid(padding=(0, 1))
        modules.add_column()
        modules.add_row(Text.from_markup("📦 [primary]Modules[/]"))
        mod_names = env.get("modules") or []
        if mod_names:
            for m in mod_names:
                modules.add_row(Text.from_markup(f"   • [muted]{m}[/]"))
        else:
            modules.add_row(
                Text.from_markup("   [warning]No modules associated.[/]")
            )
        parts.extend([Rule(style="primary"), modules])

    return Panel(Group(*parts), border_style="primary", padding=(0, 1))
