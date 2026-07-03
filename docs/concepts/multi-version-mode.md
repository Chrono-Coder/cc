# Multi-Version Mode

## The Problem

Odoo developers often work across multiple versions — a v17 client, a v18 client,
and a v19 project, each with its own checkout and port. If you keep a v17 terminal
and a v18 terminal open side by side, you don't want switching one to clobber the
"active" environment of the other.

## What It Does

Multi-version mode is **off by default**: cc tracks exactly **one** active
environment — the one you last switched to — regardless of how many Odoo versions
you have registered. `cc switch -` jumps back to the previous one.

When you **enable** it, cc keeps **one active environment per Odoo version**. Each
version has its own active slot, resolved from the version of your current
directory. Switching a v18 project sets v18's active slot and leaves v17's slot
untouched, so each version stays independently resumable. `cc stat`, the prompt
segment, and the timesheet all read the slot for the version you're currently in.

> History: cc kept a per-version active env in early versions, **dropped it in
> 3.8** (single active only), and **brought it back as an opt-in in 3.11**. The
> default is still single-active — multi-version mode is for people who genuinely
> run several versions concurrently.

## Enable It

```bash
cc config
```

Pick **Multi-version mode** from the settings picker and set it to `true`
(the `multi_version_mode` setting). Default: `false`.

## When to Use It

Enable it if you regularly keep projects on different Odoo versions active in
parallel terminals and want each version to remember its own active env. If you
only ever work on one thing at a time, leave it off — single-active is simpler and
`cc switch -` covers jumping back.

## Related

- [Projects & Environments](projects-environments.md) — the active-environment model
- [`cc switch`](../commands/switch.md) — `cc switch -` returns to the previous env
- [Settings Guide](../configuration/settings.md) — the `multi_version_mode` setting
