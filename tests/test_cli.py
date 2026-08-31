"""Command line interface."""

from __future__ import annotations

import pytest

from dca.cli import main


def test_doctor_reports_every_engine(capsys):
    exit_code = main(["doctor"])
    out = capsys.readouterr().out

    assert exit_code == 0, "a default engine is missing from the test environment"
    for engine in ("radon", "lizard", "ast", "complexipy", "pyscn", "vulture", "bandit"):
        assert engine in out
    assert "embeddings extra" in out


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
    for name in ("a", "b"):
        (tmp_path / f"{name}.py").write_text(corpus["mi_informative"], encoding="utf-8")

    assert main(["analyse", str(tmp_path), "--engines", "radon"]) == 0
    assert "lloc__radon" in capsys.readouterr().out


def test_unknown_engine_exits_with_an_error(tmp_path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")

    assert main(["analyse", str(tmp_path), "--engines", "nope"]) == 2
    assert "unknown engine" in capsys.readouterr().err


def test_missing_path_is_rejected():
    with pytest.raises(SystemExit):
        main(["analyse", "/nonexistent/path/xyz.py"])
