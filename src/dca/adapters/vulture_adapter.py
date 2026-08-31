"""vulture — dead code by heuristic.

vulture finds names that are defined and never referenced. Its method is heuristic and it
says so: every finding carries a confidence, because a name can always be reached by
``getattr``, a plugin registry, or a test file vulture was not shown.

It is kept on the subprocess path even though it is importable, so that every
findings-style engine shares one integration shape and none of them can raise inside the
host process (ADR-0003, §2.2 of the spec).

**Its results are deliberately not reconciled with pyscn's dead code** (R-22). pyscn works
from the control-flow graph and finds statements that cannot be reached; vulture works from
name resolution and finds definitions nobody uses. They answer different questions and
disagree constantly. Both are emitted, and the disagreement is a datum.

Two caveats worth knowing when reading the numbers.

**Isolation.** Analysing a fragment on its own makes almost every top-level definition look
unused, because the caller is not in the file. On single-fragment analysis these counts
describe self-containment more than they describe waste.

**Path sensitivity.** vulture applies pytest conventions to decide what is reachable:
``Test*`` classes and ``test_*`` methods are assumed to be called by a runner. The trigger
is **any component of the path**, not only the filename — ``fragment.py`` inside a
directory named ``test_stuff/`` is whitelisted just as ``test_stuff.py`` would be.

A fragment is a string with no path, so this adapter has to invent one. Both parts it
picks are deliberately neutral: the file is ``fragment.py`` and the directory is prefixed
``dca-vulture-``. Change either to something containing "test" and every count silently
drops, with nothing else looking wrong. ``test_the_vulture_adapter_uses_a_neutral_temporary_path``
guards that.

The consequence for readers: these counts are the counts for ordinary code. Measuring a
real test file through this adapter reports more dead code than
``vulture path/to/test_x.py`` does, and that gap is vulture's convention rather than an
error.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..contract import Adapter
from ..execution import responds, run, which
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

BINARY = "vulture"

#: "fragment.py:5: unused method 'deposit' (60% confidence)"
_FINDING_RE = re.compile(r"^[^:]+:(\d+):\s*unused\s+(\w+)\s+'([^']*)'\s*\((\d+)%\s*confidence\)")

_INVALID = NullSemantics.INVALID_INPUT

_SPECS = [
    MetricSpec(
        key='dead_code_items',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            'Definitions vulture found unreferenced. Counts self-containment as much as waste when '
            'a fragment is analysed alone.'
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='dead_code_high_confidence',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            'Unreferenced definitions reported at 100% confidence, where vulture is certain the '
            'name is unreachable.'
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='dead_code_min_confidence',
        granularity=Granularity.FILE,
        unit='percent',
        dtype='int',
        description='Lowest confidence among the findings. Null when there are none.',
        valid_range=(0, 100),
        null_semantics=NullSemantics.NOT_APPLICABLE,
    ),
]


class VultureAdapter(Adapter):
    name = "vulture"
    path = "subprocess"

    @property
    def version(self) -> str | None:
        binary = which(BINARY)
        if binary is None:
            return None
        result = run([binary, "--version"], timeout=15)
        if not result.ok:
            return None
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
            findings = self._run(binary, code)
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

        confidences = [c for _, _, _, c in findings]
        return AdapterResult(
            values={
                "dead_code_items": len(findings),
                "dead_code_high_confidence": sum(1 for c in confidences if c >= 100),
                # No findings means there is no minimum to report: null, not zero (R-05).
                "dead_code_min_confidence": min(confidences) if confidences else None,
            },
            raw=findings,
        )

    def _run(self, binary: str, code: str) -> list[tuple[int, str, str, int]]:
        with tempfile.TemporaryDirectory(prefix="dca-vulture-") as tmp:
            source = Path(tmp) / "fragment.py"
            source.write_text(code, encoding="utf-8")
            result = run([binary, "fragment.py"], cwd=tmp)
            if result.timed_out:
                raise TimeoutError("vulture exceeded the time budget analysing one fragment")
            # vulture exits 0 with no findings and 3 with findings; both are success. Any
            # other code with empty stdout is a real failure.
            if result.returncode not in (0, 3) and not result.stdout.strip():
                raise RuntimeError(
                    f"vulture exited {result.returncode}: {result.stderr[:200]!r}"
                )
            findings = []
            for line in result.stdout.splitlines():
                match = _FINDING_RE.match(line.strip())
                if match:
                    findings.append(
                        (int(match.group(1)), match.group(2), match.group(3), int(match.group(4)))
                    )
            return findings
