"""End-to-end behaviour of the analyser."""

from __future__ import annotations

from dca import analyse, analyse_many
from dca.core import Analyser
from dca.schema import IDENTITY_COLUMNS


def test_analyse_returns_a_typed_result_carrying_provenance(mi_informative):
    """R-17: no naked numbers. The provenance travels with the values."""
    result = analyse(mi_informative)

    assert result.provenance is not None
    assert result.provenance.analysis_chain["radon"] == "6.0.1"
    assert result.value("lloc", "radon") > 0
    assert result.code_sha256


def test_identical_code_shares_a_fingerprint(mi_informative):
    assert analyse(mi_informative).code_sha256 == analyse(mi_informative).code_sha256


def test_analyse_many_accepts_ids_or_a_sequence(corpus):
    keyed = analyse_many(corpus)
    assert len(keyed) == len(corpus)
    assert set(keyed.metrics()["fragment_id"]) == set(corpus)

    anonymous = analyse_many(list(corpus.values()))
    assert len(anonymous) == len(corpus)


def test_schema_is_stable_when_an_engine_is_absent(mi_informative):
    """R-13: restricting engines changes which columns exist, but a run never produces a
    ragged frame — every row has every column of its own schema."""
    analyser = Analyser(engines=["radon", "ast"])
    frame = analyser.analyse_many({"a": mi_informative, "b": "x = 1\n"})
    metrics = frame.metrics()

    expected = list(IDENTITY_COLUMNS) + analyser.columns()
    assert list(metrics.columns) == expected


def test_unavailable_engine_produces_nulls_not_a_crash(mi_informative):
    """Contract rule 4. pylint is not installed in the default environment, and asking for
    it must yield null columns rather than an error."""
    result = Analyser(engines=["pylint"]).analyse(mi_informative)

    assert all(
        v is None for k, v in result.metrics.items() if k.endswith("__pylint")
    )
    assert not result.degradations


def test_degradations_are_recorded_not_swallowed(mi_informative):
    """R-20: a silent degradation is a defect, so a failing engine must leave a trace."""

    class ExplodingAdapter(Analyser(engines=["radon"]).adapters[0].__class__):
        name = "radon"

        def analyse(self, code):
            return self._degraded(fragment_id="", exc=RuntimeError("boom"))

    analyser = Analyser(adapters=[ExplodingAdapter()])
    result = analyser.analyse(mi_informative, fragment_id="f1")

    assert len(result.degradations) == 1
    degradation = result.degradations[0]
    assert degradation.engine == "radon"
    assert degradation.fragment_id == "f1"
    assert "boom" in degradation.detail
    assert all(v is None for k, v in result.metrics.items() if k.endswith("__radon"))


def test_one_bad_fragment_does_not_affect_another(corpus, invalid_code):
    """ADR-0013: an export of thousands must not die because of one input."""
    frame = analyse_many({"bad": invalid_code, "good": corpus["mi_informative"]})
    metrics = frame.metrics().set_index("fragment_id")

    assert metrics.loc["good", "lloc__radon"] > 0
    assert metrics.loc["bad", "lloc__radon"] is None or metrics.loc["bad"].isna()["lloc__radon"]


def test_per_function_detail_is_preserved_alongside_the_aggregate(with_classes):
    """R-07: aggregating to mean/max/min is lossy, so the detail is exposed separately."""
    frame = analyse_many({"c": with_classes})
    functions = frame.functions()

    assert not functions.empty
    assert {"fragment_id", "engine", "name"} <= set(functions.columns)
    assert len(functions[functions["engine"] == "lizard"]) >= 3
