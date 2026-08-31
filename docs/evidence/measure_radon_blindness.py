#!/usr/bin/env python3
"""Measure radon's Halstead blindness and maintainability-index saturation.

Runs against **any** body of Python. By default it measures the open-source packages
installed in the current environment, so the result is reproducible by anyone with a
Python environment and needs no dataset to be distributed.

    python measure_radon_blindness.py                    # installed packages
    python measure_radon_blindness.py '/path/to/**/*.py' # anything else

Why: ``radon.visitors.HalsteadVisitor`` implements only ``visit_BinOp``, ``visit_UnaryOp``,
``visit_BoolOp``, ``visit_AugAssign`` and ``visit_Compare``. Assignment, calls, attribute
access, subscripting, conditional expressions and every control-flow keyword are not
operators to it. Code that computes without arithmetic therefore reports Halstead volume
zero, and ``radon.metrics.mi_compute`` short-circuits to exactly 100.0 whenever volume or
SLOC is <= 0.

The bias is systematic in the *shape* of the code, not random: it penalises programs that
call, assign and iterate rather than calculate.

Requires ``lizard >= 1.24`` for the Halstead extension (it does not exist in 1.23).
"""

from __future__ import annotations

import ast
import glob
import random
import sys

import lizard
from radon.metrics import h_visit, mi_visit

#: Nodes that do computational work, whether or not radon counts them as operators. This
#: is what separates "this code has no operators" from "radon sees no operators".
OPERATIONAL = (
    ast.Call, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Subscript, ast.Attribute,
    ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.If, ast.Return, ast.comprehension,
)

SAMPLE = 1500
ANALYZER = lizard.FileAnalyzer(lizard.get_extensions(["halstead"]))


def collect(pattern: str) -> list[str]:
    sources = []
    for path in glob.glob(pattern, recursive=True):
        try:
            source = open(path, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if not (20 < len(source) < 200_000):
            continue
        try:
            ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        sources.append(source)
    return sources


def main(pattern: str) -> int:
    sources = collect(pattern)
    if not sources:
        print(f"no parseable Python matched: {pattern}")
        return 1
    random.seed(1)  # deterministic
    sources = random.sample(sources, min(SAMPLE, len(sources)))

    measured = zero_volume = saturated = 0
    operational_in_zero: list[int] = []
    ratios: list[float] = []

    for source in sources:
        try:
            volume = h_visit(source).total.volume
            mi = mi_visit(source, True)
        except Exception:  # noqa: BLE001 - radon raises on exotic but parseable code
            continue
        measured += 1
        if volume == 0:
            zero_volume += 1
            nodes = list(ast.walk(ast.parse(source)))
            operational_in_zero.append(sum(isinstance(n, OPERATIONAL) for n in nodes))
        if mi == 100.0:
            saturated += 1
        try:
            functions = ANALYZER.analyze_source_code("s.py", source).function_list
            lizard_volume = sum(getattr(f, "halstead_volume", 0) or 0 for f in functions)
        except Exception:  # noqa: BLE001
            lizard_volume = 0
        if volume > 0 and lizard_volume > 0:
            ratios.append(lizard_volume / volume)

    print(f"files measured             : {measured}")
    print(f"radon halstead volume == 0 : {zero_volume} ({zero_volume / measured:.2%})")
    print(f"radon MI == 100.0 exactly  : {saturated} ({saturated / measured:.2%})")

    if operational_in_zero:
        operational_in_zero.sort()
        median = operational_in_zero[len(operational_in_zero) // 2]
        empty = sum(1 for x in operational_in_zero if x == 0) / len(operational_in_zero)
        print("\nof the zero-volume files:")
        print(f"  median real operational AST nodes : {median}")
        print(f"  genuinely operator-free           : {empty:.2%}")

    if ratios:
        ratios.sort()
        pick = lambda p: ratios[int(len(ratios) * p)]  # noqa: E731
        print(f"\nlizard/radon Halstead volume ratio (n={len(ratios)}):")
        print(
            f"  min {min(ratios):.2f}x | p25 {pick(0.25):.2f}x | "
            f"MEDIAN {pick(0.5):.2f}x | p75 {pick(0.75):.2f}x | max {max(ratios):.2f}x"
        )
    return 0


if __name__ == "__main__":
    default = f"{sys.prefix}/lib/python3.*/site-packages/**/*.py"
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else default))
