"""pylint — global score and per-category counts. Optional, subprocess only.

pylint is **GPLv2+**. Importing it from this library would, with high probability, force
the whole package to be copyleft, which would prevent its use inside other academic
artifacts under different licences. It is therefore reached only as a subprocess, behind
the ``pylint`` extra, and the licence CI job asserts it never enters the import tree
(ADR-0011).

Two design constraints follow from what pylint is:

* **Grouped by category, never one column per message code.** pylint has hundreds of codes
  and they change between minor releases; a column per code would be a schema of hundreds
  of columns that breaks on every upgrade. The four categories are stable.
* **Low priority.** pylint is a findings tool, not a measurement tool, and its contribution
  to a metric vector was always marginal. It is included because the LLM-code literature
  (SWE-CI, Licorish et al.) uses the pylint score as a comparison variable, so being able
  to reproduce that comparison is worth one optional adapter.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path

from ..contract import Adapter
from ..execution import responds, run, which
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

BINARY = "pylint"

_SCORE_RE = re.compile(r"rated at (-?\d+\.\d+)/10")

_INVALID = NullSemantics.INVALID_INPUT

_SPECS = [
    MetricSpec(
        key='pylint_score',
        granularity=Granularity.FILE,
        unit='score',
        dtype='float',
        description="pylint's global rating out of 10. Can be negative on heavily flagged code.",
        valid_range=(None, 10),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='pylint_convention',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Convention messages (naming, layout).',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='pylint_refactor',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Refactor messages (code smells).',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='pylint_warning',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Warning messages (likely mistakes).',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='pylint_error',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Error messages (probable bugs).',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
]

_CATEGORY_BY_LETTER = {
    "C": "pylint_convention",
    "R": "pylint_refactor",
    "W": "pylint_warning",
    "E": "pylint_error",
    "F": "pylint_error",  # fatal rolls into error; it is rare and always a hard failure
}


class PylintAdapter(Adapter):
    name = "pylint"
    path = "subprocess"

    @property
    def version(self) -> str | None:
        binary = which(BINARY)
        if binary is None:
            return None
        result = run([binary, "--version"], timeout=30)
        if not result.ok:
            return None
        first = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        parts = first.split()
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
            return AdapterResult(values=self._run(binary, code))
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

    def _run(self, binary: str, code: str) -> dict[str, float | int | None]:
        with tempfile.TemporaryDirectory(prefix="dca-pylint-") as tmp:
            source = Path(tmp) / "fragment.py"
            source.write_text(code, encoding="utf-8")
            result = run(
                [binary, "--output-format=json", "--score=y", "--persistent=no", "fragment.py"],
                cwd=tmp,
                timeout=60,  # pylint is markedly slower than the other engines
            )
            if result.timed_out:
                raise TimeoutError("pylint exceeded the time budget analysing one fragment")

            counts = dict.fromkeys(set(_CATEGORY_BY_LETTER.values()), 0)
            try:
                messages = result.json()
            except ValueError:
                messages = []
            if isinstance(messages, list):
                for message in messages:
                    letter = str(message.get("message-id", ""))[:1]
                    key = _CATEGORY_BY_LETTER.get(letter)
                    if key:
                        counts[key] += 1

            # The score is only on stderr's summary line with --output-format=json.
            score_match = _SCORE_RE.search(result.stderr) or _SCORE_RE.search(result.stdout)
            values: dict[str, float | int | None] = dict(counts)
            values["pylint_score"] = float(score_match.group(1)) if score_match else None
            return values
