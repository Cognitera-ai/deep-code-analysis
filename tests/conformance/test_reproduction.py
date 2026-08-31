"""Reproduction tests: the adapter returns exactly what its engine returns.

This is the only thing the conformance suite may assert about correctness, and the
distinction matters (ADR-0010). There is **no oracle**: validating against radon and
validating against lizard are mutually incompatible goals, because they differ by a median
factor of 14 on the same metric over the same corpus.

So a valid assertion here has the form "reproduces radon 6.0.1 within epsilon over corpus
C". An assertion of the form "the Halstead volume computed by this package is correct" is
forbidden, because nobody can make it.

What these tests genuinely catch is adapter distortion: a rounding bug, a units mistake, an
aggregation applied where it should not be.
"""

from __future__ import annotations

import pytest

from dca.adapters.ast_adapter import AstAdapter
from dca.adapters.lizard_adapter import LizardAdapter
from dca.adapters.radon_adapter import RadonAdapter


def test_radon_reproduces_raw_metrics(corpus):
    """Size metrics must pass through untouched."""
    from radon.raw import analyze

    adapter = RadonAdapter()
    for name, code in corpus.items():
        result = adapter.analyse(code)
        if result.values.get("lloc") is None:
            continue
        expected = analyze(code)
        assert result.values["lloc"] == expected.lloc, name
        assert result.values["sloc"] == expected.sloc, name
        assert result.values["total_lines"] == expected.loc, name
        assert result.values["blank_lines"] == expected.blank, name


def test_radon_raw_invariant_holds(corpus):
    """radon asserts sloc + blank + multi + single_comments == loc. If our pass-through
    broke that, the numbers would be internally inconsistent."""
    adapter = RadonAdapter()
    for name, code in corpus.items():
        v = adapter.analyse(code).values
        if v.get("lloc") is None:
            continue
        assert (
            v["sloc"] + v["blank_lines"] + v["multi_line_comments"] + v["single_comments"]
            == v["total_lines"]
        ), name


def test_radon_reproduces_halstead(corpus):
    """Including, and especially, the zeros."""
    from radon.metrics import h_visit

    adapter = RadonAdapter()
    for name, code in corpus.items():
        result = adapter.analyse(code)
        if result.values.get("halstead_volume") is None:
            continue
        expected = h_visit(code).total
        assert result.values["halstead_volume"] == pytest.approx(expected.volume, abs=1e-6), name
        assert result.values["halstead_h1"] == expected.h1, name
        assert result.values["halstead_n2"] == expected.N2, name


def test_radon_reproduces_maintainability_index(corpus):
    from radon.metrics import mi_visit

    adapter = RadonAdapter()
    for name, code in corpus.items():
        result = adapter.analyse(code)
        if result.values.get("maintainability_index") is None:
            continue
        assert result.values["maintainability_index"] == pytest.approx(
            mi_visit(code, True), abs=1e-6
        ), name


def test_lizard_reproduces_per_function_metrics(corpus):
    import lizard

    analyzer = lizard.FileAnalyzer(lizard.get_extensions(["halstead"]))
    adapter = LizardAdapter()
    for name, code in corpus.items():
        result = adapter.analyse(code)
        if result.values.get("function_count") is None:
            continue
        expected = analyzer.analyze_source_code("fragment.py", code)
        assert result.values["function_count"] == len(expected.function_list), name
        assert result.values["nloc"] == expected.nloc, name


def test_ast_metrics_are_recomputable_by_hand(corpus):
    """The one adapter that computes rather than delegates has no upstream to check
    against, so its definitions are checked directly."""
    import ast

    adapter = AstAdapter()
    for name, code in corpus.items():
        result = adapter.analyse(code)
        if result.values.get("total_nodes") is None:
            continue
        tree = ast.parse(code)
        nodes = list(ast.walk(tree))
        assert result.values["total_nodes"] == len(nodes), name
        assert result.values["call_count"] == sum(isinstance(n, ast.Call) for n in nodes), name
        assert result.values["functiondef_count"] == sum(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in nodes
        ), name
