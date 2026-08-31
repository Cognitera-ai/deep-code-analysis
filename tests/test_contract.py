"""The adapter contract, enforced for every adapter rather than trusted.

These are parameterised over the whole registry, so a new adapter is held to the same rules
the day it is added without anyone remembering to write tests for it.
"""

from __future__ import annotations

import pytest

from dca.adapters import ALL_ADAPTERS, build
from dca.contract import Adapter, aggregate
from dca.schema import AdapterResult, Granularity, MetricSpec

ADAPTERS = [cls() for cls in ALL_ADAPTERS]
IDS = [a.name for a in ADAPTERS]


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_declares_identity(adapter: Adapter):
    assert adapter.name and adapter.name.isidentifier()
    assert adapter.path in ("import", "subprocess")


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_is_available_never_raises(adapter: Adapter):
    assert isinstance(adapter.is_available(), bool)


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_declared_metrics_are_well_formed(adapter: Adapter):
    specs = adapter.declared_metrics
    assert specs, f"{adapter.name} declares no metrics"
    keys = [s.key for s in specs]
    assert len(keys) == len(set(keys)), f"{adapter.name} declares a duplicate key"
    for spec in specs:
        assert isinstance(spec, MetricSpec)
        assert spec.key and not spec.key.startswith("_")
        assert isinstance(spec.granularity, Granularity)
        # Every field here reaches user-facing documentation, so an undescribed metric is
        # a metric nobody can use.
        assert spec.description.strip(), f"{adapter.name}.{spec.key} has no description"
        assert spec.description.strip().endswith("."), (
            f"{adapter.name}.{spec.key} description is not a sentence"
        )
        assert spec.unit.strip()
        assert spec.dtype in ("int", "float", "bool")


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_analyse_never_raises_on_hostile_input(adapter: Adapter):
    """Nothing a caller can pass may propagate an exception (R-19)."""
    for code in ["", "   ", "def broken(", "\x00\x01\x02", "x = 1", "とても長い" * 100]:
        result = adapter.analyse(code)
        assert isinstance(result, AdapterResult)


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_invalid_python_yields_all_nulls(adapter: Adapter, invalid_code: str):
    """R-06: invalid input produces nulls, never zeros."""
    result = adapter.analyse(invalid_code)
    assert all(v is None for v in result.values.values()), (
        f"{adapter.name} returned a non-null value for invalid Python"
    )


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_emits_only_declared_keys(adapter: Adapter, mi_informative: str):
    """An adapter that emitted an undeclared key would silently widen the schema."""
    if not adapter.is_available():
        pytest.skip(f"{adapter.name} not installed")
    declared = {s.key for s in adapter.declared_metrics}
    emitted = set(adapter.analyse(mi_informative).values)
    assert emitted <= declared, f"{adapter.name} emitted undeclared keys: {emitted - declared}"


@pytest.mark.parametrize("adapter", ADAPTERS, ids=IDS)
def test_adapter_does_not_import_another_adapter(adapter: Adapter):
    """Rule 2 of the contract: divergence is a core concern, not an adapter's (R-08)."""
    import inspect
    from pathlib import Path

    source = Path(inspect.getfile(type(adapter))).read_text(encoding="utf-8")
    others = {a.name for a in ADAPTERS} - {adapter.name}
    for other in others:
        assert f"from .{other}_adapter" not in source, f"{adapter.name} imports {other}"
        assert f"import {other}_adapter" not in source


def test_unknown_engine_name_is_rejected():
    """A typo in --engines must fail loudly, not silently analyse with fewer engines."""
    with pytest.raises(ValueError, match="unknown engine"):
        build(["radon", "definitely-not-an-engine"])


def test_aggregate_empty_series_is_null_not_zero():
    """R-05: no functions is an absence, not a measurement of zero."""
    assert aggregate([], "x") == {"x_mean": None, "x_max": None, "x_min": None}
    assert aggregate([2, 4], "x") == {"x_mean": 3.0, "x_max": 4, "x_min": 2}
