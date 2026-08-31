"""bandit — security smells.

bandit walks the AST looking for patterns with known security consequences: ``eval`` on
untrusted input, ``subprocess`` with ``shell=True``, weak hashes, hardcoded credentials.
Every finding carries both a severity and a *confidence*, and the two are independent —
bandit reports a high-severity pattern it is unsure about differently from one it is
certain of, and collapsing them loses that.

Both axes are therefore emitted in full. That is three severity counts and three confidence
counts rather than one score, which is more columns but keeps the distinction bandit went to
the trouble of making.

Relevant to generated code specifically: models reproduce insecure idioms from their
training data, so these counts are a response variable in their own right, not just a
hygiene check.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ..contract import Adapter
from ..execution import run, which
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

BINARY = "bandit"

_INVALID = NullSemantics.INVALID_INPUT

_SPECS = [
    MetricSpec(
        key='security_issues',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Total security findings.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_severity_low',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings bandit rates low severity.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_severity_medium',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings bandit rates medium severity.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_severity_high',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings bandit rates high severity.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_confidence_low',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings bandit is least sure about. Independent of severity.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_confidence_medium',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings at medium confidence.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='security_confidence_high',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Findings bandit is most sure about.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
]


class BanditAdapter(Adapter):
    name = "bandit"
    path = "subprocess"

    @property
    def version(self) -> str | None:
        binary = which(BINARY)
        if binary is None:
            return None
        result = run([binary, "--version"], timeout=20)
        if not result.ok:
            return None
        # "bandit 1.9.4" possibly followed by a python version line
        first = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
        parts = first.split()
        return parts[-1] if parts else None

    def is_available(self) -> bool:
        return which(BINARY) is not None

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

        totals = (report.get("metrics") or {}).get("_totals") or {}

        def count(key: str) -> int:
            value = totals.get(key, 0)
            return int(value) if isinstance(value, (int, float)) else 0

        return AdapterResult(
            values={
                "security_issues": len(report.get("results") or []),
                "security_severity_low": count("SEVERITY.LOW"),
                "security_severity_medium": count("SEVERITY.MEDIUM"),
                "security_severity_high": count("SEVERITY.HIGH"),
                "security_confidence_low": count("CONFIDENCE.LOW"),
                "security_confidence_medium": count("CONFIDENCE.MEDIUM"),
                "security_confidence_high": count("CONFIDENCE.HIGH"),
            },
            raw=report,
        )

    def _run(self, binary: str, code: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="dca-bandit-") as tmp:
            source = Path(tmp) / "fragment.py"
            source.write_text(code, encoding="utf-8")
            result = run([binary, "-f", "json", "-q", "fragment.py"], cwd=tmp)
            if result.timed_out:
                raise TimeoutError("bandit exceeded the time budget analysing one fragment")
            # bandit exits 1 when it found something. Only an empty stdout is a failure.
            if not result.stdout.strip():
                raise RuntimeError(
                    f"bandit exited {result.returncode} with no report: {result.stderr[:200]!r}"
                )
            return result.json()
