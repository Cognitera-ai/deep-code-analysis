"""The lexical vocabulary metrics.

These exist because radon's Halstead reports zero on code that calls, assigns and iterates
rather than calculates — about one file in five of ordinary Python, and far more of
generated code. The quantities Halstead was reaching for are real; they just need counting
over every token instead of five AST node types.
"""

from __future__ import annotations

import pytest

from dca.adapters.lexical_adapter import LexicalAdapter

SAMPLE = '''import collections
from math import sqrt


def sum_of_multiples(limit, divisors):
    multiples = set()
    for divisor in divisors:
        multiples.update(range(divisor, limit, divisor))
    return sum(multiples)


counts = collections.Counter([1, 2, 2])
print(counts.most_common())
'''


@pytest.fixture(scope="module")
def adapter() -> LexicalAdapter:
    return LexicalAdapter()


def test_it_measures_where_radon_reports_nothing(adapter):
    """The founding argument for this adapter, in one assertion.

    radon sees no operators in this code and reports a Halstead volume of zero. The
    vocabulary is plainly not empty, and this says so.
    """
    from radon.metrics import h_visit

    assert h_visit(SAMPLE).total.volume == 0

    values = adapter.analyse(SAMPLE).values
    assert values["distinct_tokens"] > 20
    assert values["lexical_tokens"] > 40
    assert values["distinct_identifiers"] > 10


def test_it_can_never_be_zero_on_a_non_empty_program(adapter):
    """The property that makes it usable where Halstead is not."""
    for code in ("x = 1\n", "print(1)\n", "class A:\n    pass\n"):
        values = adapter.analyse(code).values
        assert values["distinct_tokens"] > 0, code
        assert values["distinct_identifiers"] > 0, code


def test_comments_are_not_vocabulary(adapter):
    """A comment is words the author wrote, not words the program is made of.

    Including them would let a heavily commented file outscore a dense one on lexical
    diversity, which would be measuring the writing rather than the code.
    """
    bare = adapter.analyse("x = 1\ny = 2\n").values
    commented = adapter.analyse("# a long explanatory comment here\nx = 1\ny = 2\n").values

    assert bare["lexical_tokens"] == commented["lexical_tokens"]
    assert bare["distinct_tokens"] == commented["distinct_tokens"]


def test_the_breakdown_separates_kinds_of_name(adapter):
    values = adapter.analyse(SAMPLE).values

    assert values["distinct_functions_defined"] == 1        # sum_of_multiples
    assert values["distinct_imports"] == 3                  # collections, math, sqrt
    assert values["distinct_calls"] >= 5                    # set, update, range, sum, print…
    assert values["distinct_attributes"] >= 2               # .update, .most_common…
    assert values["distinct_variables"] >= 4                # limit, divisors, multiples…


def test_a_name_may_count_in_more_than_one_kind(adapter):
    """Deliberate: `count` can be both a variable and an attribute, and collapsing that
    would lose the distinction rather than resolve it."""
    values = adapter.analyse("count = 0\ncount = data.count\n").values

    assert values["distinct_variables"] >= 1
    assert values["distinct_attributes"] >= 1


def test_diversity_is_distinct_over_total(adapter):
    values = adapter.analyse(SAMPLE).values
    expected = values["distinct_tokens"] / values["lexical_tokens"]

    assert values["type_token_ratio"] == pytest.approx(expected, abs=1e-6)
    assert 0 < values["type_token_ratio"] <= 1


def test_invalid_python_yields_nulls(adapter, invalid_code):
    assert all(v is None for v in adapter.analyse(invalid_code).values.values())
