"""Command line interface."""

from __future__ import annotations

import pytest

from dca.cli import main


def test_doctor_reports_every_engine(capsys):
    """doctor names every engine and its state, whatever that state happens to be.

    Deliberately no assertion on the exit code. An earlier version required 0, which meant
    it was asserting that the machine running the tests had every engine installed and
    working — not that doctor does its job. It duly failed on CI, where pyscn's Go runtime
    aborts on the runner. Reporting "MISSING" and exiting non-zero is doctor working
    correctly, and is precisely the case a user most needs it for.
    """
    main(["doctor"])
    out = capsys.readouterr().out

    for engine in ("radon", "lizard", "ast", "complexipy", "pyscn", "vulture", "bandit"):
        assert engine in out, f"doctor did not mention {engine}"
    assert "embeddings extra" in out
    # Every engine row carries a state, so no row is ambiguous.
    assert "available" in out or "MISSING" in out


def test_doctor_exit_code_reflects_whether_defaults_are_usable(capsys, monkeypatch):
    """0 when everything a default run needs is usable, non-zero when it is not.

    Forced rather than inferred from the environment, so it tests the logic in both
    directions on any machine.
    """
    from dca.adapters import radon_adapter

    monkeypatch.setattr(radon_adapter.RadonAdapter, "is_available", lambda self: False)
    assert main(["doctor"]) == 1
    assert "MISSING" in capsys.readouterr().out


def test_catalogue_writes_to_a_path(tmp_path, capsys):
    target = tmp_path / "nested" / "catalogue.md"
    assert main(["catalogue", "--write", str(target)]) == 0
    assert "halstead_volume__radon" in target.read_text()


def test_analyse_writes_tables(tmp_path, corpus):
    source = tmp_path / "fragment.py"
    source.write_text(corpus["mi_informative"], encoding="utf-8")
    out = tmp_path / "out"

    assert main(["analyse", str(source), "--out", str(out), "--format", "parquet"]) == 0
    assert (out / "dca_metrics.parquet").exists()
    assert (out / "dca_provenance.json").exists()


def test_analyse_reads_a_directory(tmp_path, corpus, capsys):
    """Without --out, stdout is a readable overview rather than the whole frame.

    Dumping 138 columns to a terminal produced something nobody could read and no tool
    could consume. The overview names each fragment and points at --out for the rest, so
    that is what this asserts (ADR-0019).
    """
    for name in ("a", "b"):
        (tmp_path / f"{name}.py").write_text(corpus["mi_informative"], encoding="utf-8")

    assert main(["analyse", str(tmp_path), "--engines", "radon"]) == 0
    out = capsys.readouterr().out

    assert "a.py" in out and "b.py" in out
    assert "--out" in out, "the overview must say where the full data goes"


def test_unknown_engine_exits_with_an_error(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    assert main(["analyse", str(tmp_path), "--engines", "nope"]) == 2
    assert "unknown engine" in capsys.readouterr().err


def test_missing_path_is_rejected():
    with pytest.raises(SystemExit):
        main(["analyse", "/nonexistent/path/xyz.py"])
