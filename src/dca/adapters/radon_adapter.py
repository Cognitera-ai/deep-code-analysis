"""radon — size, cyclomatic complexity, Halstead and maintainability.

radon is the de facto standard for these metrics in Python and is what the literature this
package addresses actually uses. It is also **stalled** (no release since 2023-03-26,
single maintainer) and carries two documented pathologies this adapter is obliged to
surface rather than smooth over:

* **Halstead blindness.** ``radon.visitors.HalsteadVisitor`` implements exactly five
  visitors — ``visit_BinOp``, ``visit_UnaryOp``, ``visit_BoolOp``, ``visit_AugAssign``,
  ``visit_Compare``. Assignment, calls, attribute access, subscripting, ``IfExp`` and every
  control-flow keyword are not operators to it. Code that computes without arithmetic
  therefore reports volume 0: about a fifth of ordinary open-source Python, and roughly
  93 % of those files do contain real operators.
* **MI saturation.** ``mi_compute`` returns exactly 100.0 through two distinct paths: a
  short-circuit when volume or SLOC is <= 0, and an upper clamp. On ordinary open-source
  Python that is about one file in five, for a reason unrelated to maintainability.

Neither is a bug we may fix — reimplementing would produce a fourth opinion with no
authority (ADR-0001). Both are *reported*: the saturation flag is mandatory, and lizard's
reading of Halstead is emitted alongside so the divergence is visible (ADR-0004).
"""

from __future__ import annotations

from radon.complexity import ComplexityVisitor
from radon.metrics import h_visit, mi_visit
from radon.raw import analyze as radon_raw

from ..contract import Adapter
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

_SPECS = [
    # ── size ────────────────────────────────────────────────────────────────────────
    MetricSpec(
        key='lloc',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Logical lines of code: one per statement.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='sloc',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Source lines of code: non-blank, non-comment lines.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='comments',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Lines containing a comment.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='single_comments',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Lines that are only a comment, docstrings included.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='multi_line_comments',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Lines inside multi-line strings.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='blank_lines',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Blank lines.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='total_lines',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Every line in the fragment.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    # ── cyclomatic complexity ───────────────────────────────────────────────────────
    MetricSpec(
        key='cyclomatic_complexity_mean',
        granularity=Granularity.FILE,
        unit='paths',
        dtype='float',
        description=(
            "Mean McCabe complexity across the fragment's blocks; the module body when it defines "
            "none (see cc_imputed_module_level)."
        ),
        valid_range=(1, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='cyclomatic_complexity_max',
        granularity=Granularity.FILE,
        unit='paths',
        dtype='int',
        description='Highest McCabe complexity of any block.',
        valid_range=(1, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='cyclomatic_complexity_module',
        granularity=Granularity.FILE,
        unit='paths',
        dtype='int',
        description=(
            'McCabe complexity of the module body alone, excluding anything inside a function.'
        ),
        valid_range=(1, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='cc_imputed_module_level',
        granularity=Granularity.FILE,
        unit='flag',
        dtype='bool',
        description=(
            "True when the fragment defines no function or class, so both CC readings are the "
            "module body's rather than per-function."
        ),
        valid_range=(0, 1),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    # ── Halstead ────────────────────────────────────────────────────────────────────
    MetricSpec(
        key='halstead_h1',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Distinct operators, as radon counts them (five AST node types only).',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_h2',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Distinct operands.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_n1',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Total operator occurrences.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_n2',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Total operand occurrences.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_vocabulary',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Distinct operators plus distinct operands.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_calculated_length',
        granularity=Granularity.FILE,
        unit='count',
        dtype='float',
        description=(
            'Halstead predicted length from the vocabulary alone. Comparing it against the '
            'measured length is his own consistency check: a program far from its '
            'prediction uses its vocabulary unusually.'
        ),
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_length',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Total operator plus operand occurrences.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_volume',
        granularity=Granularity.FILE,
        unit='bits',
        dtype='float',
        description=(
            'Halstead volume. Zero whenever radon recognises no operators, which is common and '
            'usually not a real absence — see halstead_volume_is_zero.'
        ),
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_difficulty',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description='Halstead difficulty: operator variety against operand repetition.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_effort',
        granularity=Granularity.FILE,
        unit='bits',
        dtype='float',
        description='Halstead effort: difficulty times volume.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_time',
        granularity=Granularity.FILE,
        unit='seconds',
        dtype='float',
        description="Halstead's estimated implementation time.",
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_bugs',
        granularity=Granularity.FILE,
        unit='count',
        dtype='float',
        description="Halstead's estimated delivered bugs.",
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_volume_is_zero',
        granularity=Granularity.FILE,
        unit='flag',
        dtype='bool',
        description=(
            'True when radon found no operators at all. On generated code this is usually '
            'instrument blindness rather than genuinely operator-free code.'
        ),
        valid_range=(0, 1),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    # ── maintainability ─────────────────────────────────────────────────────────────
    MetricSpec(
        key='maintainability_index',
        granularity=Granularity.FILE,
        unit='index',
        dtype='float',
        description=(
            'Coleman et al. maintainability index, normalised to 0-100. Saturates at exactly 100 '
            'whenever Halstead volume is zero.'
        ),
        valid_range=(0, 100),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='maintainability_index_saturated',
        granularity=Granularity.FILE,
        unit='flag',
        dtype='bool',
        description=(
            'True when the index is exactly 100, meaning it carries no information for this '
            'fragment. Mandatory companion to the index.'
        ),
        valid_range=(0, 1),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='maintainability_saturation_path',
        granularity=Granularity.FILE,
        unit='code',
        dtype='int',
        description=(
            'How the index reached 100: 0 not saturated, 1 short-circuit on zero volume or SLOC, 2 '
            'upper clamp.'
        ),
        valid_range=(0, 2),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
]


class RadonAdapter(Adapter):
    name = "radon"
    path = "import"

    def is_available(self) -> bool:
        try:
            radon_raw("x = 1\n")
            return True
        except Exception:  # noqa: BLE001 - availability must never raise
            return False

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        return list(_SPECS)

    def analyse(self, code: str) -> AdapterResult:
        if not is_valid_python(code):
            return self._null_result()
        try:
            return AdapterResult(values=self._measure(code))
        except Exception as exc:  # noqa: BLE001 - R-19: never raise upward
            return self._degraded(fragment_id="", exc=exc)

    # ── internals ───────────────────────────────────────────────────────────────────

    def _measure(self, code: str) -> dict[str, float | int | bool | None]:
        raw = radon_raw(code)
        values: dict[str, float | int | bool | None] = {
            "lloc": raw.lloc,
            "sloc": raw.sloc,
            # radon separates "lines containing a comment" from "lines that are only a
            # comment, docstrings included"; its raw analyser asserts
            # sloc + blank + multi + single_comments == loc, so the two are not
            # interchangeable and both are reported.
            "comments": raw.comments,
            "single_comments": raw.single_comments,
            "multi_line_comments": raw.multi,
            "blank_lines": raw.blank,
            "total_lines": raw.loc,
        }
        values.update(self._complexity(code))
        halstead = self._halstead(code)
        values.update(halstead)
        values.update(self._maintainability(code, halstead["halstead_volume"], raw.sloc))
        return values

    def _complexity(self, code: str) -> dict[str, float | int | bool]:
        """Cyclomatic complexity, with module-level imputation (R-04).

        One visitor serves both readings: ``.blocks`` is every def/class/method with its
        own CC, ``.complexity`` is the CC of the module body itself.

        When a fragment defines nothing, radon reports no per-block CC. We do **not** emit
        null. The module body *is* a block: McCabe's number for a straight-line script is 1
        (one path), and each module-level branch adds one, which is exactly
        ``visitor.complexity``.

        This matters more than it looks. Leaving it null makes the missingness itself a
        treatment effect: in the corpus that motivated this package, per-function CC was
        present for 57 % of one model's output and 0.4 % of another's, so any analysis of
        the non-null subset was silently conditioning on the model. The flag keeps the two
        populations separable so a study can report them apart.
        """
        visitor = ComplexityVisitor.from_code(code)
        per_block = [b.complexity for b in visitor.blocks]
        module_cc = visitor.complexity
        if per_block:
            return {
                "cyclomatic_complexity_mean": round(sum(per_block) / len(per_block), 4),
                "cyclomatic_complexity_max": max(per_block),
                "cyclomatic_complexity_module": module_cc,
                "cc_imputed_module_level": False,
            }
        return {
            "cyclomatic_complexity_mean": float(module_cc),
            "cyclomatic_complexity_max": module_cc,
            "cyclomatic_complexity_module": module_cc,
            "cc_imputed_module_level": True,
        }

    def _halstead(self, code: str) -> dict[str, float | int | bool]:
        total = h_visit(code).total
        volume = round(total.volume, 6)
        return {
            "halstead_h1": total.h1,
            "halstead_h2": total.h2,
            "halstead_n1": total.N1,
            "halstead_n2": total.N2,
            "halstead_vocabulary": total.vocabulary,
            "halstead_length": total.length,
            "halstead_calculated_length": round(total.calculated_length, 6),
            "halstead_volume": volume,
            "halstead_difficulty": round(total.difficulty, 6),
            "halstead_effort": round(total.effort, 6),
            "halstead_time": round(total.time, 6),
            "halstead_bugs": round(total.bugs, 6),
            "halstead_volume_is_zero": volume == 0,
        }

    def _maintainability(
        self, code: str, volume: float, sloc: int
    ) -> dict[str, float | int | bool | None]:
        """The index plus its mandatory saturation flag.

        The flag is not optional decoration. ``mi_compute`` reaches exactly 100.0 by two
        routes and a consumer reading the bare column cannot tell a maintainable fragment
        from an unmeasurable one. We recover which route was taken from the inputs, since
        radon does not report it: volume or SLOC at zero is the short-circuit, anything
        else reaching 100 is the upper clamp.
        """
        try:
            mi = mi_visit(code, True)
        except Exception:  # noqa: BLE001 - radon raises on exotic-but-parseable code
            return {
                "maintainability_index": None,
                "maintainability_index_saturated": None,
                "maintainability_saturation_path": None,
            }
        saturated = mi == 100.0
        if not saturated:
            path = 0
        elif volume <= 0 or sloc <= 0:
            path = 1
        else:
            path = 2
        return {
            "maintainability_index": round(mi, 6),
            "maintainability_index_saturated": saturated,
            "maintainability_saturation_path": path,
        }
