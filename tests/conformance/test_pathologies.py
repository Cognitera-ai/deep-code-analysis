"""Each documented pathology, pinned to the corpus fragment that exhibits it.

These are the tests that would fail if the package started smoothing over the engine
behaviour it exists to report. A regression here means the package has begun to lie
comfortably rather than report awkwardly.
"""

from __future__ import annotations

import pytest

from dca.core import Analyser


def test_radon_halstead_blindness_is_visible(halstead_blind):
    """radon reports zero on code with obvious operator content; lizard does not.

    This single assertion is the package's founding observation. If it ever fails, either
    radon changed its visitor set (interesting, report upstream) or the adapter started
    papering over the difference (a defect).
    """
    result = Analyser(engines=["radon", "lizard", "ast"]).analyse(halstead_blind)

    assert result.value("halstead_volume", "radon") == 0
    assert result.value("halstead_volume", "lizard") > 0
    # And the code is demonstrably not operator-free.
    assert result.value("operational_node_count", "ast") >= 4
    assert result.metrics["halstead_volume__divergent"] is True
    # Zero versus non-zero has no ratio: it is stronger than any ratio could express.
    assert result.metrics["halstead_volume__delta_ratio"] is None


def test_mi_saturation_is_flagged_via_short_circuit(corpus):
    """Path 1: volume is zero, so mi_compute returns 100.0 without computing."""
    result = Analyser(engines=["radon"]).analyse(corpus["mi_saturated_shortcircuit"])

    assert result.value("maintainability_index", "radon") == 100.0
    assert result.value("maintainability_index_saturated", "radon") is True
    assert result.value("maintainability_saturation_path", "radon") == 1
    assert result.value("halstead_volume_is_zero", "radon") is True


def test_informative_fragment_is_not_flagged(mi_informative):
    """The control case. Without it, a bug that flagged everything would look correct."""
    result = Analyser(engines=["radon"]).analyse(mi_informative)

    assert result.value("halstead_volume", "radon") > 0
    assert result.value("maintainability_index", "radon") < 100.0
    assert result.value("maintainability_index_saturated", "radon") is False
    assert result.value("maintainability_saturation_path", "radon") == 0


def test_flat_script_imputes_cc_and_flags_it(flat_script):
    """R-04. Null would make the missingness a treatment effect: smaller models write flat
    scripts far more often, so conditioning on 'CC exists' silently conditions on model."""
    result = Analyser(engines=["radon"]).analyse(flat_script)

    assert result.value("cc_imputed_module_level", "radon") is True
    assert result.value("cyclomatic_complexity_mean", "radon") >= 1
    assert result.value("cyclomatic_complexity_mean", "radon") is not None


def test_lizard_is_not_a_substitute_for_radon_on_flat_scripts(flat_script):
    """The reason 'just use lizard' does not work.

    lizard measures Halstead only inside functions. On a corpus that is mostly flat
    scripts, switching engines would trade radon's zeros for lizard's nulls.
    """
    result = Analyser(engines=["radon", "lizard"]).analyse(flat_script)

    assert result.value("halstead_volume", "lizard") is None
    assert result.value("halstead_volume", "radon") is not None
    assert result.value("function_count", "lizard") == 0


def test_deeply_nested_code_does_not_raise(corpus):
    """Deeply nested but valid code is measured, not degraded."""
    result = Analyser(engines=["ast"]).analyse(corpus["deeply_nested"])

    depth = result.value("ast_depth", "ast")
    assert isinstance(depth, int) and depth > 100
    assert not result.degradations


def test_depth_is_independent_of_the_recursion_limit(corpus):
    """Demonstrates why the depth computation is iterative rather than recursive.

    Lowering the recursion limit is the honest way to show this: a recursive walk consumes
    one frame per level, so its safety margin is whatever the host's limit happens to be —
    and a caller can lower it, as this test does. The iterative walk has no such margin to
    exhaust, and returns the same answer at any limit.
    """
    import ast
    import sys

    from dca.adapters.ast_adapter import AstAdapter

    code = corpus["deeply_nested"]

    def recursive_depth(node):
        children = list(ast.iter_child_nodes(node))
        return 1 + max((recursive_depth(c) for c in children), default=0)

    original = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(120)
        with pytest.raises(RecursionError):
            recursive_depth(ast.parse(code))
        # Same input, same lowered limit, no failure.
        assert AstAdapter().analyse(code).values["ast_depth"] > 100
    finally:
        sys.setrecursionlimit(original)


def test_invalid_python_yields_a_row_of_nulls(invalid_code):
    """R-06: the row is emitted, not dropped, so tables stay aligned by fragment id."""
    result = Analyser().analyse(invalid_code)

    assert result.is_valid_python is False
    metric_values = [
        v for k, v in result.metrics.items()
        if not k.endswith(("__delta_ratio", "__divergent"))
    ]
    assert all(v is None for v in metric_values)


def test_null_is_never_silently_zero(flat_script):
    """R-05, stated as a property: a fragment with no functions must have null
    per-function metrics, not zeros that would drag every mean downward."""
    result = Analyser(engines=["lizard"]).analyse(flat_script)

    for key in ("avg_token_count_mean", "function_length_mean", "halstead_difficulty"):
        assert result.value(key, "lizard") is None, key


def test_oo_metrics_are_null_without_classes_and_present_with_them(flat_script, with_classes):
    """A semantic null: 'this fragment has no classes' is not 'cohesion is zero'."""
    analyser = Analyser(engines=["pyscn"])
    if not analyser.available_engines().get("pyscn"):
        pytest.skip("pyscn not installed")

    flat = analyser.analyse(flat_script)
    classes = analyser.analyse(with_classes)

    assert flat.value("lcom_mean", "pyscn") is None
    assert flat.value("cbo_mean", "pyscn") is None
    assert classes.value("class_count", "pyscn") == 1
    # Ledger's describe() touches no attribute, so the class splits into components.
    assert classes.value("lcom_mean", "pyscn") > 1


def test_dead_code_detectors_are_not_reconciled(corpus):
    """R-22: pyscn works from the CFG, vulture from name resolution. They answer different
    questions and both answers are emitted."""
    analyser = Analyser(engines=["pyscn", "vulture"])
    available = analyser.available_engines()
    if not (available.get("pyscn") and available.get("vulture")):
        pytest.skip("pyscn and vulture both required")

    result = analyser.analyse(corpus["dead_code"])
    assert result.value("dead_code_findings", "pyscn") is not None
    assert result.value("dead_code_items", "vulture") is not None
