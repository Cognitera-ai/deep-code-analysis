"""Output tables and writers."""

from __future__ import annotations

import json

import pandas as pd

from dca import analyse_many


def test_csv_and_parquet_round_trip(tmp_path, corpus):
    """A-14. Parquet is authoritative because CSV cannot preserve types (R-18)."""
    frame = analyse_many(corpus)

    parquet_files = frame.to_parquet(tmp_path / "pq")
    csv_files = frame.to_csv(tmp_path / "csv")

    original = frame.metrics()
    from_parquet = pd.read_parquet(parquet_files["metrics"])

    assert list(from_parquet.columns) == list(original.columns)
    assert len(from_parquet) == len(original)
    # Parquet keeps the distinction between an integer column with nulls and a float one;
    # CSV does not, which is why only Parquet is authoritative.
    pd.testing.assert_frame_equal(from_parquet, original)
    assert csv_files["metrics"].exists()


def test_provenance_is_written_as_json_in_both_formats(tmp_path, corpus):
    """Provenance stays JSON even in CSV mode: flattening a nested envelope into one row
    would lose the structure that makes it auditable."""
    frame = analyse_many(corpus)
    files = frame.to_csv(tmp_path)

    envelope = json.loads(files["provenance"].read_text())
    assert envelope["package"]["schema_version"]
    assert envelope["analysis_chain"]["radon"] == "6.0.1"
    assert envelope["interpreter"]["python_version"]
    assert envelope["inputs"]["fragment_count"] == len(corpus)


def test_generation_block_is_omitted_when_absent(corpus):
    """An absent block means 'not model-generated'. A block of nulls would mean
    'model-generated, parameters unknown', which is a different claim."""
    frame = analyse_many(corpus)
    assert "generation" not in frame.provenance_dict()


def test_generation_block_is_recorded_when_supplied(corpus):
    from dca import GenerationProvenance

    frame = analyse_many(
        corpus, generation=GenerationProvenance(model="qwen2.5:7b", temperature=0.7, seed=42)
    )
    generation = frame.provenance_dict()["generation"]

    assert generation["model"] == "qwen2.5:7b"
    assert generation["temperature"] == 0.7
    assert generation["seed"] == 42


def test_null_rates_and_divergence_summary_are_usable(corpus):
    frame = analyse_many(corpus)

    rates = frame.null_rates()
    assert rates.is_monotonic_decreasing

    summary = frame.divergence_summary()
    assert set(summary.columns) == {
        "metric", "compared", "divergent", "divergent_rate", "ratio_median", "ratio_max"
    }


def test_empty_tables_are_not_written(tmp_path, mi_informative):
    """A run with no degradations should not leave an empty degradations file to puzzle
    over."""
    frame = analyse_many({"a": mi_informative})
    files = frame.to_csv(tmp_path)

    assert "metrics" in files
    assert "degradations" not in files
