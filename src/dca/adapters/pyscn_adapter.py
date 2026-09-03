"""pyscn — OO design metrics, control-flow structure and CFG-based dead code.

pyscn closes a gap that was genuinely open until 2025. Coupling between objects (CBO) and
lack of cohesion (LCOM) had proper implementations for Java and C# and nothing maintained
for Python; the original design for this package budgeted an entire phase to implementing
them by hand. pyscn (MIT, created August 2025) emits both, plus CFG nodes and edges,
nesting depth, dead code found through the control-flow graph, and APTED clone detection.
That phase was deleted (ADR-0006).

It is a Go binary with a Python wrapper exposing only ``main()``, so integration is by
subprocess. Two operational details it does not advertise:

* It writes its JSON to ``.pyscn/reports/<timestamp>.json`` **relative to the working
  directory**, not to stdout. We therefore run it in a throwaway directory and read the
  report back, which also keeps it from littering the caller's tree.
* ``cbo`` defaults to ``show_zeros: false``, so a class with no coupling is absent from the
  per-class list while still counted in the summary. Summary figures are the reliable read.

Still uncovered by any Python tool, and left as v2 roadmap: DIT (depth of inheritance) and
RFC (response for a class).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ..contract import Adapter
from ..execution import responds, run, which
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

BINARY = "pyscn"
_SELECT = "complexity,deadcode,cbo,lcom,clones"

_NA = NullSemantics.NOT_APPLICABLE
_INVALID = NullSemantics.INVALID_INPUT

_SPECS = [
    MetricSpec(
        key='cbo_mean',
        granularity=Granularity.CLASS,
        unit='count',
        dtype='float',
        description="Mean coupling between objects across the fragment's classes.",
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cbo_max',
        granularity=Granularity.CLASS,
        unit='count',
        dtype='int',
        description='Highest coupling between objects of any class.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='lcom_mean',
        granularity=Granularity.CLASS,
        unit='count',
        dtype='float',
        description=(
            'Mean LCOM4: connected components of the method-attribute graph. 1 is cohesive; higher '
            'means the class splits into unrelated groups.'
        ),
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='lcom_max',
        granularity=Granularity.CLASS,
        unit='count',
        dtype='int',
        description='Highest LCOM4 of any class.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='class_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Classes pyscn analysed.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='cognitive_complexity_mean',
        granularity=Granularity.FUNCTION,
        unit='points',
        dtype='float',
        description=(
            'Mean cognitive complexity per function, as pyscn computes it. Known to differ from '
            'complexipy on the same code.'
        ),
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cyclomatic_complexity_mean',
        granularity=Granularity.FUNCTION,
        unit='paths',
        dtype='float',
        description='Mean McCabe complexity per function, as pyscn computes it.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='cyclomatic_complexity_max',
        granularity=Granularity.FUNCTION,
        unit='paths',
        dtype='int',
        description='Highest McCabe complexity of any function, as pyscn computes it.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='nesting_depth_mean',
        granularity=Granularity.FUNCTION,
        unit='levels',
        dtype='float',
        description='Mean nesting depth per function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='nesting_depth_max',
        granularity=Granularity.FUNCTION,
        unit='levels',
        dtype='int',
        description='Deepest nesting of any function.',
        valid_range=(0, None),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='dead_code_findings',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            "Unreachable code blocks found through the control-flow graph. A different method from "
            "vulture's heuristic, and deliberately not reconciled with it (R-22)."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='dead_code_ratio',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description='Share of CFG blocks that are unreachable.',
        valid_range=(0, 1),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='clone_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            'Code fragments pyscn found to be clones of another, by tree edit distance '
            '(APTED). Within one analysed fragment this is self-similarity — two functions '
            'that resemble each other — because the unit of analysis is a single fragment '
            'rather than a repository.'
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='clone_pairs',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Pairs of fragments judged similar enough to be clones of each other.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='clone_groups',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            'Clusters of mutually similar fragments. Three near-identical functions are '
            'one group, not three pairs.'
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='clone_similarity_mean',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description=(
            'Mean similarity among the clone pairs found. Null when none were found, '
            'because there is no mean of nothing.'
        ),
        valid_range=(0, 1),
        null_semantics=_NA,
    ),
    MetricSpec(
        key='clone_fragments_analysed',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            'Fragments pyscn considered for clone detection. The denominator the clone '
            'counts should be read against.'
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='function_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Functions pyscn parsed.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='sloc',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Source lines of code, as pyscn counts them.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='lloc',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Logical lines of code, as pyscn counts them.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='comment_lines',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Comment lines, as pyscn counts them.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='docstring_lines',
        granularity=Granularity.FILE,
        unit='lines',
        dtype='int',
        description='Docstring lines.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
]


def _num(value: object) -> float | int | None:
    """Coerce a JSON scalar to a number, or None. pyscn emits ints where a float is
    expected and nulls where a section found nothing."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    return None


class PyscnAdapter(Adapter):
    name = "pyscn"
    path = "subprocess"

    @property
    def version(self) -> str | None:
        binary = which(BINARY)
        if binary is None:
            return None
        result = run([binary, "--version"], timeout=15)
        if not result.ok:
            return None
        # "pyscn version 1.30.0"
        parts = result.stdout.strip().split()
        return parts[-1] if parts else None

    def is_available(self) -> bool:
        """Present *and* working. A binary that aborts on startup is not availability."""
        binary = which(BINARY)
        return binary is not None and responds(binary, "--version")

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        return list(_SPECS)

    def analyse(self, code: str) -> AdapterResult:
        if not is_valid_python(code):
            return self._null_result()
        binary = which(BINARY)
        if binary is None:
            return self._null_result()
        try:
            report = self._run(binary, code)
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)
        if report is None:
            return self._null_result()
        return AdapterResult(values=self._extract(report), raw=report)

    # ── internals ───────────────────────────────────────────────────────────────────

    def _run(self, binary: str, code: str) -> dict | None:
        """Run pyscn in a throwaway directory and read back the report it writes there."""
        with tempfile.TemporaryDirectory(prefix="dca-pyscn-") as tmp:
            source = Path(tmp) / "fragment.py"
            source.write_text(code, encoding="utf-8")
            result = run(
                [binary, "analyze", "--json", "--no-open", "--select", _SELECT, "fragment.py"],
                cwd=tmp,
            )
            if result.timed_out:
                raise TimeoutError("pyscn exceeded the time budget analysing one fragment")
            reports = sorted((Path(tmp) / ".pyscn" / "reports").glob("*.json"))
            if not reports:
                # A non-zero exit with no report is a real failure; an exit with no report
                # on valid input means pyscn declined to analyse, which is not our error.
                if not result.ok:
                    raise RuntimeError(
                        f"pyscn exited {result.returncode} without a report: "
                        f"{result.stderr[:200]!r}"
                    )
                return None
            return json.loads(reports[-1].read_text(encoding="utf-8"))

    def _extract(self, report: dict) -> dict[str, float | int | bool | None]:
        complexity = report.get("complexity") or {}
        csum = complexity.get("summary") or {}
        raw_metrics = complexity.get("raw_metrics_summary") or {}
        dead = (report.get("dead_code") or {}).get("summary") or {}
        clones = (report.get("clone") or {}).get("statistics") or {}
        cbo = (report.get("cbo") or {}).get("summary") or {}
        lcom = (report.get("lcom") or {}).get("summary") or {}

        # Aggregate from the per-function list, not from pyscn's own summary. The summary
        # counts the module body as a function named "<module>" (complexity 1, cognitive 0)
        # and averages it in, so a file with one function of cognitive complexity 4 reports
        # an average of 2. That is not a disagreement about the metric — pyscn and
        # complexipy agree on every real function — it is a disagreement about what a
        # "function" is, and it was masquerading as an 80 % divergence until diagnosed.
        real = [
            f for f in (complexity.get("functions") or [])
            if isinstance(f, dict)
            and f.get("name") != "<module>"
            and f.get("scope_kind") != "module"
        ]
        ccs = [_num((f.get("metrics") or {}).get("complexity")) for f in real]
        ccs = [c for c in ccs if c is not None]
        cogs = [_num((f.get("metrics") or {}).get("cognitive_complexity")) for f in real]
        cogs = [c for c in cogs if c is not None]
        nests = [_num((f.get("metrics") or {}).get("nesting_depth")) for f in real]
        nests = [n for n in nests if n is not None]

        functions_parsed = len(real)
        classes_analyzed = (
            _num(lcom.get("classes_analyzed")) or _num(cbo.get("classes_analyzed")) or 0
        )
        has_functions = bool(functions_parsed)
        has_classes = bool(classes_analyzed)

        def mean(xs):
            return round(sum(xs) / len(xs), 4) if xs else None

        return {
            # Class-level metrics are null, not zero, when there are no classes (R-05).
            "cbo_mean": _num(cbo.get("average_cbo")) if has_classes else None,
            "cbo_max": _num(cbo.get("max_cbo")) if has_classes else None,
            "lcom_mean": _num(lcom.get("average_lcom")) if has_classes else None,
            "lcom_max": _num(lcom.get("max_lcom")) if has_classes else None,
            "class_count": int(classes_analyzed),
            "cognitive_complexity_mean": mean(cogs),
            "cyclomatic_complexity_mean": mean(ccs),
            "cyclomatic_complexity_max": max(ccs) if ccs else None,
            "nesting_depth_mean": mean(nests),
            "nesting_depth_max": max(nests) if nests else None,
            "clone_count": _num(clones.get("total_clones")),
            "clone_pairs": _num(clones.get("total_clone_pairs")),
            "clone_groups": _num(clones.get("total_clone_groups")),
            # No clones means there is no mean similarity to report — null, not zero, which
            # would read as "these fragments are maximally dissimilar".
            "clone_similarity_mean": (
                _num(clones.get("average_similarity"))
                if _num(clones.get("total_clone_pairs"))
                else None
            ),
            "clone_fragments_analysed": _num(clones.get("total_fragments")),
            "dead_code_findings": _num(dead.get("total_findings")),
            "dead_code_ratio": _num(dead.get("overall_dead_ratio")),
            "function_count": int(functions_parsed),
            "sloc": _num(raw_metrics.get("sloc")),
            "lloc": _num(raw_metrics.get("lloc")),
            "comment_lines": _num(raw_metrics.get("comment_lines")),
            "docstring_lines": _num(raw_metrics.get("docstring_lines")),
        }
