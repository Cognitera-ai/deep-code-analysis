"""Schema rules that hold regardless of which engines ran."""

from __future__ import annotations

import pytest

from dca.schema import (
    IDENTITY_COLUMNS,
    column_name,
    delta_column,
    divergent_column,
    split_column,
)


def test_column_name_requires_an_engine():
    """R-03: the bare metric name is forbidden."""
    assert column_name("halstead_volume", "radon") == "halstead_volume__radon"
    with pytest.raises(ValueError, match="bare metric name is forbidden"):
        column_name("halstead_volume", "")


def test_split_column_round_trips():
    assert split_column("halstead_volume__radon") == ("halstead_volume", "radon")
    assert split_column("fragment_id") == ("fragment_id", None)


def test_divergence_column_helpers():
    assert delta_column("halstead_volume") == "halstead_volume__delta_ratio"
    assert divergent_column("halstead_volume") == "halstead_volume__divergent"


def test_no_metric_column_lacks_an_engine(analyser):
    """A-04: every metric column has an identifiable producing engine."""
    for column in analyser.columns():
        key, engine = split_column(column)
        assert engine, f"{column} has no engine suffix"
        assert key not in IDENTITY_COLUMNS


def test_schema_is_fixed_regardless_of_engine_subset():
    """R-13: the column list depends on configuration, not on what happened to run."""
    from dca.core import Analyser

    a = Analyser(engines=["radon", "ast"])
    first = a.columns()
    second = a.columns()
    assert first == second
    assert all(
        c.endswith(("__radon", "__ast")) or "__delta_ratio" in c or "__divergent" in c
        for c in first
    )
