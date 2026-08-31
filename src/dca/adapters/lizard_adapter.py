"""lizard — per-function metrics, and a second reading of Halstead.

lizard matters here for two independent reasons.

**Per-function metrics.** Token count, parameter count and function length are its own
contribution; radon has no equivalent.

**A second opinion on Halstead.** This is the point of including it at all. Measured over
1500 files of installed open-source Python, lizard and radon diverge on Halstead volume by
a **median factor of 14x**, with a long tail into the thousands. The package emits both and
their ratio rather than picking a winner (ADR-0004).

Two limitations that must not be smoothed over:

* **lizard measures Halstead only inside functions.** For a flat script it returns nothing.
  It is therefore *not* a drop-in replacement for radon: on code that is mostly flat
  scripts, switching engines trades radon's zeros for lizard's nulls.
* **``fan_in`` / ``fan_out`` always return 0.** The fields exist; the values are not
  computed. They are deliberately not exposed.

The ``-ENS`` (nested structures) extension is also deliberately unused: its counter leaks
across functions *and across files*, and the reported value changes with the order of
files on the command line. ``max_nesting_depth`` from the base analysis is sound.
"""

from __future__ import annotations

import lizard

from ..contract import Adapter, aggregate
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

#: The Halstead extension only exists from 1.24 (R-23). Below that, importing this module
#: must fail loudly: silently emitting nulls would be indistinguishable from real zeros,
#: which is precisely the confusion this package exists to prevent.
MIN_LIZARD_VERSION = (1, 24)


def _check_version() -> None:
    raw = getattr(lizard, "version", "0")
    try:
        parts = tuple(int(p) for p in str(raw).split(".")[:2])
    except ValueError:  # pragma: no cover - a version string we cannot read
        parts = (0, 0)
    if parts < MIN_LIZARD_VERSION:
        raise ImportError(
            f"dca requires lizard >= {'.'.join(map(str, MIN_LIZARD_VERSION))} for the "
            f"Halstead extension, found {raw}. Emitting nulls instead would be "
            "indistinguishable from real zeros (R-23)."
        )


_check_version()

_ANALYZER = lizard.FileAnalyzer(lizard.get_extensions(["halstead"]))

_NA = NullSemantics.NOT_APPLICABLE

_SPECS = [
    MetricSpec(
        key='function_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Functions lizard found in the fragment.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='avg_token_count_mean',
        granularity=Granularity.FUNCTION,
        unit='tokens',
        dtype='float',
        description='Mean token count per function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='avg_token_count_max',
        granularity=Granularity.FUNCTION,
        unit='tokens',
        dtype='int',
        description='Largest token count of any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='avg_token_count_min',
        granularity=Granularity.FUNCTION,
        unit='tokens',
        dtype='int',
        description='Smallest token count of any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='avg_param_count_mean',
        granularity=Granularity.FUNCTION,
        unit='count',
        dtype='float',
        description='Mean parameter count per function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='avg_param_count_max',
        granularity=Granularity.FUNCTION,
        unit='count',
        dtype='int',
        description='Largest parameter count of any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='avg_param_count_min',
        granularity=Granularity.FUNCTION,
        unit='count',
        dtype='int',
        description='Smallest parameter count of any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='function_length_mean',
        granularity=Granularity.FUNCTION,
        unit='lines',
        dtype='float',
        description='Mean function length in non-comment lines.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='function_length_max',
        granularity=Granularity.FUNCTION,
        unit='lines',
        dtype='int',
        description='Longest function in non-comment lines.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='function_length_min',
        granularity=Granularity.FUNCTION,
        unit='lines',
        dtype='int',
        description='Shortest function in non-comment lines.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cyclomatic_complexity_mean',
        granularity=Granularity.FUNCTION,
        unit='paths',
        dtype='float',
        description='Mean McCabe complexity per function, as lizard counts it.',
        valid_range=(1, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cyclomatic_complexity_max',
        granularity=Granularity.FUNCTION,
        unit='paths',
        dtype='int',
        description='Highest McCabe complexity of any function, as lizard counts it.',
        valid_range=(1, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cyclomatic_complexity_min',
        granularity=Granularity.FUNCTION,
        unit='paths',
        dtype='int',
        description='Lowest McCabe complexity of any function.',
        valid_range=(1, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='max_nesting_depth',
        granularity=Granularity.FUNCTION,
        unit='levels',
        dtype='int',
        description='Deepest nesting level reached in any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='nloc',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Non-comment lines of code for the whole fragment.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='token_count',
        granularity=Granularity.FILE,
        unit='tokens',
        dtype='int',
        description='Total tokens in the fragment.',
        valid_range=(0, None),
        null_semantics=NullSemantics.INVALID_INPUT,
    ),
    MetricSpec(
        key='halstead_volume',
        granularity=Granularity.FUNCTION,
        unit='bits',
        dtype='float',
        description=(
            'Halstead volume summed across functions. Null for flat scripts: lizard only measures '
            'inside functions.'
        ),
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='halstead_difficulty',
        granularity=Granularity.FUNCTION,
        unit='ratio',
        dtype='float',
        description='Mean Halstead difficulty across functions.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='halstead_effort',
        granularity=Granularity.FUNCTION,
        unit='bits',
        dtype='float',
        description='Halstead effort summed across functions.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='halstead_length',
        granularity=Granularity.FUNCTION,
        unit='count',
        dtype='int',
        description='Halstead length summed across functions.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='halstead_vocabulary',
        granularity=Granularity.FUNCTION,
        unit='count',
        dtype='int',
        description='Mean Halstead vocabulary across functions.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
]


class LizardAdapter(Adapter):
    name = "lizard"
    path = "import"

    def is_available(self) -> bool:
        try:
            _ANALYZER.analyze_source_code("probe.py", "def f():\n    return 1\n")
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
            return self._measure(code)
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

    def _measure(self, code: str) -> AdapterResult:
        analysed = _ANALYZER.analyze_source_code("fragment.py", code)
        funcs = list(analysed.function_list)

        values: dict[str, float | int | bool | None] = {
            "function_count": len(funcs),
            "nloc": analysed.nloc,
            "token_count": getattr(analysed, "token_count", None),
        }

        if not funcs:
            # No functions is an absence, not a zero (R-05). Every per-function key stays
            # null — including Halstead, which is exactly why lizard cannot replace radon.
            for spec in _SPECS:
                values.setdefault(spec.key, None)
            for spec in _SPECS:
                if spec.granularity is Granularity.FUNCTION:
                    values[spec.key] = None
            return AdapterResult(values=values)

        values.update(aggregate([f.token_count for f in funcs], "avg_token_count"))
        values.update(aggregate([len(f.parameters) for f in funcs], "avg_param_count"))
        values.update(aggregate([f.nloc for f in funcs], "function_length"))
        values.update(aggregate([f.cyclomatic_complexity for f in funcs], "cyclomatic_complexity"))
        values["max_nesting_depth"] = max(
            (getattr(f, "max_nesting_depth", 0) or 0) for f in funcs
        )

        volumes = [getattr(f, "halstead_volume", None) for f in funcs]
        volumes = [v for v in volumes if v is not None]
        difficulties = [getattr(f, "halstead_difficulty", None) for f in funcs]
        difficulties = [d for d in difficulties if d is not None]
        efforts = [getattr(f, "halstead_effort", None) for f in funcs]
        efforts = [e for e in efforts if e is not None]
        lengths = [getattr(f, "halstead_length", None) for f in funcs]
        lengths = [n for n in lengths if n is not None]
        vocabs = [getattr(f, "halstead_vocabulary", None) for f in funcs]
        vocabs = [v for v in vocabs if v is not None]

        # Volume, effort and length are extensive (they sum over functions); difficulty and
        # vocabulary are intensive (they average). Summing a difficulty would make a
        # fragment look harder merely for having more functions.
        values["halstead_volume"] = round(sum(volumes), 6) if volumes else None
        values["halstead_effort"] = round(sum(efforts), 6) if efforts else None
        values["halstead_length"] = sum(lengths) if lengths else None
        values["halstead_difficulty"] = (
            round(sum(difficulties) / len(difficulties), 6) if difficulties else None
        )
        values["halstead_vocabulary"] = round(sum(vocabs) / len(vocabs), 6) if vocabs else None

        functions = [
            {
                "name": f.name,
                "start_line": f.start_line,
                "end_line": f.end_line,
                "nloc": f.nloc,
                "token_count": f.token_count,
                "param_count": len(f.parameters),
                "cyclomatic_complexity": f.cyclomatic_complexity,
                "max_nesting_depth": getattr(f, "max_nesting_depth", None),
                "halstead_volume": getattr(f, "halstead_volume", None),
                "halstead_difficulty": getattr(f, "halstead_difficulty", None),
            }
            for f in funcs
        ]
        return AdapterResult(values=values, functions=functions)
