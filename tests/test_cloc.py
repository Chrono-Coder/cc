"""
Tests for the cloc output parser (ClocCommand.run_cloc).

We mock subprocess.run to feed known odoo-cloc output and verify
the parsed table printed to stdout.
"""
from unittest.mock import patch, MagicMock

import pytest


# Real odoo cloc format: Module  Line  Other  Code  (4 columns per module row)
# Total line: 3 numbers only (no module name)
SAMPLE_CLOC_OUTPUT = """\
Odoo cloc                                                   Line   Other    Code
--------------------------------------------------------------------------------
sale_custom                                                  120      25      95
purchase_custom                                               80      18      62
hr_payroll_ext                                               200      30     170
--------------------------------------------------------------------------------
                                                             400      73     327
"""

SAMPLE_CLOC_SINGLE = """\
Odoo cloc                                                   Line   Other    Code
--------------------------------------------------------------------------------
sale_custom                                                  120      25      95
--------------------------------------------------------------------------------
                                                             120      25      95
"""

SAMPLE_CLOC_EMPTY = ""


def _run_cloc(cmd_title, cmd, stdout):
    """Instantiate ClocCommand minimally and call run_cloc with mocked subprocess."""
    from cc.commands.odoo.cloc_command import ClocCommand

    cloc = object.__new__(ClocCommand)

    fake_result = MagicMock()
    fake_result.stdout = stdout
    fake_result.stderr = ""

    with patch("subprocess.run", return_value=fake_result):
        cloc.run_cloc(cmd_title, cmd)


def test_cloc_parses_multiple_modules(capsys):
    _run_cloc("Test Report", "fake cmd", SAMPLE_CLOC_OUTPUT)
    out = capsys.readouterr().out

    assert "sale_custom" in out
    assert "purchase_custom" in out
    assert "hr_payroll_ext" in out
    # Code column (last value per row)
    assert "95" in out
    assert "62" in out
    assert "170" in out
    assert "TOTAL" in out
    assert "327" in out


def test_cloc_parses_single_module(capsys):
    _run_cloc("Single", "fake cmd", SAMPLE_CLOC_SINGLE)
    out = capsys.readouterr().out

    assert "sale_custom" in out
    assert "95" in out
    assert "TOTAL" in out


def test_cloc_empty_output(capsys):
    _run_cloc("Empty", "fake cmd", SAMPLE_CLOC_EMPTY)
    out = capsys.readouterr().out

    # Should print the title but no module rows
    assert "Empty" in out
    assert "TOTAL" not in out


def test_cloc_skips_header_and_separator_lines(capsys):
    _run_cloc("Test", "fake cmd", SAMPLE_CLOC_OUTPUT)
    out = capsys.readouterr().out

    # "Odoo cloc" header and "---" separators should not appear as module names
    assert "Odoo cloc" not in out


def test_cloc_truncates_long_module_name(capsys):
    long_name = "a" * 60
    output = f"""\
Odoo cloc                                                   Line   Other    Code
--------------------------------------------------------------------------------
{long_name}                                                  100      20      80
--------------------------------------------------------------------------------
                                                             100      20      80
"""
    _run_cloc("Long", "fake cmd", output)
    out = capsys.readouterr().out

    # Long names should be truncated (rich renders ellipsis as "…")
    assert "…" in out
    assert long_name not in out  # full 60-char name should not survive intact
    assert "80" in out


def test_cloc_total_line_format(capsys):
    """Total line has 3 numbers (no module name) — should show as TOTAL."""
    _run_cloc("Totals", "fake cmd", SAMPLE_CLOC_OUTPUT)
    out = capsys.readouterr().out

    lines = [l.strip() for l in out.splitlines() if "TOTAL" in l]
    assert len(lines) == 1
    assert "327" in lines[0]
