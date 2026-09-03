"""Divergences that are understood, pinned so they stay understood.

Each test here records a place where two engines give different numbers for the same
metric, together with the *reason* — which is the difference between a finding and an
anecdote. If any of these ever starts passing the other way, an engine changed behaviour,
and the documentation that explains the divergence needs to change with it.

Every case was found on real code and reduced to the smallest fragment that shows it.
"""

from __future__ import annotations

import lizard
import pytest
from radon.complexity import ComplexityVisitor
from radon.raw import analyze

from dca.adapters.pyscn_adapter import PyscnAdapter
from dca.core import Analyser

needs_pyscn = pytest.mark.skipif(
    not PyscnAdapter().is_available(), reason="pyscn not installed or not runnable here"
)


def test_boolean_operators_are_branches_for_radon_and_lizard_but_not_pyscn():
    """The oldest McCabe ambiguity, and it is a specification difference, not a bug.

    McCabe counted decision points. Whether `a or b` is one decision or two is a choice
    every implementation makes: radon and lizard count each boolean operator as a branch,
    which is also what a person counting paths through the code arrives at; pyscn counts
    the `if` alone. Lincke, Lundberg and Löwe (ISSTA 2008) list exactly this as a source of
    inter-tool variation. Neither reading is wrong; they measure slightly different things
    under the same name.
    """
    code = "def f(a, b, c):\n    if a or b or c:\n        return 1\n    return 0\n"

    radon_cc = ComplexityVisitor.from_code(code).blocks[0].complexity
    lizard_cc = lizard.analyze_file.analyze_source_code("f.py", code).function_list[0].cyclomatic_complexity

    assert radon_cc == 4          # 1 + if + or + or
    assert lizard_cc == 4         # independent tokeniser, same convention

    if PyscnAdapter().is_available():
        pyscn_cc = PyscnAdapter().analyse(code).values["cyclomatic_complexity_max"]
        assert pyscn_cc == 2      # 1 + if; the boolean sequence is not counted


@needs_pyscn
def test_pyscn_does_not_compute_module_level_complexity():
    """A flat script has a control-flow graph too, but pyscn reports 1 for it.

    radon imputes the module body's McCabe number when there is no function — a script
    with one `for` and one `if ... or ...` has four paths, and radon says so. pyscn assigns
    the module scope a complexity of 1 regardless. For a corpus that is mostly flat scripts
    this is the single largest source of cyclomatic disagreement, and it is entirely about
    *what gets measured*, not how.
    """
    code = "total = 0\nfor i in range(10):\n    if i % 3 == 0 or i % 5 == 0:\n        total += i\n"
    result = Analyser(engines=["radon", "pyscn"]).analyse(code)

    assert result.value("cc_imputed_module_level", "radon") is True
    assert result.value("cyclomatic_complexity_mean", "radon") == 4
    # No function, so pyscn has nothing but the module scope: null rather than 1, because
    # the adapter reports the absence instead of pyscn's placeholder.
    assert result.value("cyclomatic_complexity_mean", "pyscn") is None


@needs_pyscn
def test_cognitive_complexity_agrees_once_the_module_scope_is_excluded():
    """pyscn and complexipy agree on every real function. They only *appeared* to disagree
    because pyscn's own summary averaged a "<module>" pseudo-function of complexity 0 into
    the mean, halving it on any file with one function plus a call at the bottom. The
    adapter now aggregates from the function list and skips that entry; this test is what
    keeps the two engines looking as aligned as they are.
    """
    code = (
        "def corpus_case(limit):\n"
        "    total = 0\n"
        "    for num in range(1, limit):\n"
        "        if num % 3 == 0 or num % 5 == 0:\n"
        "            total += num\n"
        "    return total\n"
        "\n"
        "print(corpus_case(1000))\n"
    )
    result = Analyser(engines=["complexipy", "pyscn"]).analyse(code)

    # Sonar, by hand: for (+1) + nested if (+1, +1 nesting) + boolean sequence (+1) = 4.
    assert result.value("cognitive_complexity_mean", "complexipy") == 4
    assert result.value("cognitive_complexity_mean", "pyscn") == 4
    assert result.metrics["cognitive_complexity_mean__divergent"] is False


def test_radon_logical_lines_can_exceed_source_lines():
    """LLOC > SLOC looks like a bug and is not: a comprehension is a statement of its own.

    radon counts the `for` inside a comprehension as a logical line, so one physical line
    holding a dict comprehension is two logical lines. That follows its documented rule and
    matches a hand count of statements. The invariant a careless reader would assume —
    lloc <= sloc — simply does not hold, and this test exists so nobody re-adds it.
    """
    code = (
        'sequence = "0011"\n'
        "distinct = set(sequence)\n"
        "freq = {s: sequence.count(s) for s in distinct}\n"
        "\n"
        "print(freq)\n"
    )
    raw = analyze(code)
    assert raw.sloc == 4
    assert raw.lloc == 5          # the comprehension's `for` is the fifth
    assert raw.lloc > raw.sloc


@needs_pyscn
def test_pyscn_lloc_is_a_different_quantity_from_radon_lloc():
    """Same name, different definition. radon's LLOC is one per statement, and it matches
    a hand count; pyscn's is closer to a non-blank source line count and equals its own
    SLOC most of the time. The schema keeps both under `lloc` with the engine suffix, so
    the disagreement is visible rather than silently resolved in either's favour."""
    code = "x = 1\nfor i in range(3):\n    if i:\n        x += i\n    else:\n        x -= i\nprint(x)\n"
    result = Analyser(engines=["radon", "pyscn"]).analyse(code)

    assert result.value("lloc", "radon") == 7    # x=, for, if, +=, else, -=, print — hand count
    assert result.value("lloc", "pyscn") is not None
    assert result.value("lloc", "pyscn") != result.value("lloc", "radon")
    assert result.metrics["lloc__divergent"] is True
