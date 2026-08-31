"""Coloured output, and the plain-text path that must never be worse than informative."""

from __future__ import annotations

import pytest

from dca import console as ui

DOCTOR_ROWS = [
    {"name": "radon", "path": "import", "status": "available", "version": "6.0.1"},
    {"name": "pyscn", "path": "subprocess", "status": "MISSING", "version": "-"},
    {"name": "pylint", "path": "subprocess", "status": "optional, off", "version": "-"},
]


def test_null_and_zero_render_differently():
    """The distinction the whole schema is built on must survive being displayed.

    A table that renders both as an empty cell erases it, and a reader would have no way
    to tell "this engine measured zero" from "this engine could not measure".
    """
    assert ui._fmt(None) == "—"
    assert ui._fmt(0) == "0"
    assert ui._fmt(0.0) == "0"
    assert ui._fmt(None) != ui._fmt(0)


def test_booleans_read_as_words():
    assert ui._fmt(True) == "yes"
    assert ui._fmt(False) == "no"


def test_severity_escalates_with_the_ratio():
    assert ui._severity(1.1, False) == "green"
    assert ui._severity(2.0, True) == "yellow"
    assert ui._severity(20.0, True) == "bold red"


def test_absent_versus_present_gets_its_own_colour():
    """No ratio exists for it, and it is the strongest disagreement there is — so it must
    not be rendered as merely 'green because there is no number'."""
    assert ui._severity(None, True) == "bold magenta"


def test_identifiers_are_shortened_from_the_tail():
    """The informative part of a path is its end."""
    short = ui._short("/very/long/prefix/that/nobody/reads/pkg/module.py")
    assert short.endswith("pkg/module.py")
    assert len(short) <= 40


def test_every_printer_works_without_rich(monkeypatch, capsys):
    """The tool must run when the tui extra is absent. A research tool that refuses to
    work because a presentation library is missing has its priorities backwards.
    """
    monkeypatch.setattr(ui, "RICH", False)

    ui.print_doctor(DOCTOR_ROWS, "0.1.0", embeddings=False)
    ui.print_divergence(
        [{"metric": "halstead_volume", "compared": 5, "divergent": 5,
          "divergent_rate": 1.0, "ratio_median": 9.1, "ratio_max": 31.0}]
    )
    ui.print_overview(
        [{"fragment": "a/b.py", "valid": True, "lloc": 10, "cc": 2.0, "divergent": 3}], 138
    )
    out = capsys.readouterr().out

    # Plain text, but no information lost.
    assert "radon" in out and "MISSING" in out
    assert "halstead_volume" in out
    assert "b.py" in out and "138" in out


@pytest.mark.skipif(not ui.RICH, reason="needs the tui extra")
def test_rich_output_contains_the_same_facts(capsys):
    ui.print_doctor(DOCTOR_ROWS, "0.1.0", embeddings=True)
    out = capsys.readouterr().out

    assert "radon" in out and "pyscn" in out
    assert "MISSING" in out
    assert "available" in out
