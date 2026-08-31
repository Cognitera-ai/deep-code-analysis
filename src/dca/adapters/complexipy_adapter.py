"""complexipy — cognitive complexity.

Cognitive complexity is Sonar's metric: unlike McCabe it weights *nesting*, so a deeply
nested branch costs more than a flat one, which is closer to how a reader experiences
difficulty. The definition is freely implementable — complexipy, pyscn and Melevir all
implement it independently. The white paper's text is copyrighted and is not reproduced
here; only the metric is used.

complexipy is chosen over Melevir's ``cognitive_complexity`` for the import path because it
is actively maintained (the alternative has had no release since 2022) and exposes a real
API rather than a single function.

**There is no canonical implementation for Python.** complexipy and pyscn return 15 and 16
for the same method. Both are emitted; the disagreement is a measurement, not a bug to
reconcile (ADR-0004).
"""

from __future__ import annotations

import complexipy

from ..contract import Adapter, aggregate
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

_SPECS = [
    MetricSpec(
        key='cognitive_complexity',
        granularity=Granularity.FILE,
        unit='points',
        dtype='int',
        description=(
            "Cognitive complexity of the whole fragment, weighting nested control flow "
            "more heavily than flat control flow."
        ),
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='cognitive_complexity_mean',
        granularity=Granularity.FUNCTION,
        unit='points',
        dtype='float',
        description='Mean cognitive complexity per function.',
        valid_range=(0, None),
        null_semantics=NullSemantics.NOT_APPLICABLE,
    ),
    MetricSpec(
        key='cognitive_complexity_max',
        granularity=Granularity.FUNCTION,
        unit='points',
        dtype='int',
        description='Highest cognitive complexity of any function.',
        valid_range=(0, None),
        null_semantics=NullSemantics.NOT_APPLICABLE,
    ),
    MetricSpec(
        key='cognitive_complexity_min',
        granularity=Granularity.FUNCTION,
        unit='points',
        dtype='int',
        description='Lowest cognitive complexity of any function.',
        valid_range=(0, None),
        null_semantics=NullSemantics.NOT_APPLICABLE,
    ),
]


class ComplexipyAdapter(Adapter):
    name = "complexipy"
    path = "import"

    def is_available(self) -> bool:
        try:
            complexipy.code_complexity("x = 1\n")
            return True
        except Exception:  # noqa: BLE001
            return False

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        return list(_SPECS)

    def analyse(self, code: str) -> AdapterResult:
        if not is_valid_python(code):
            return self._null_result()
        try:
            result = complexipy.code_complexity(code)
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

        values: dict[str, float | int | bool | None] = {
            "cognitive_complexity": result.complexity
        }
        functions = list(getattr(result, "functions", None) or [])
        # A flat script has whole-fragment complexity but no per-function series; those
        # keys stay null rather than zero (R-05).
        values.update(aggregate([f.complexity for f in functions], "cognitive_complexity"))
        return AdapterResult(
            values=values,
            functions=[{"name": f.name, "cognitive_complexity": f.complexity} for f in functions],
            raw=result,
        )
