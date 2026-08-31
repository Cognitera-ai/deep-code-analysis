"""prospector — aggregated findings across many linters. Optional, subprocess only.

prospector is the closest thing this ecosystem has to a precedent for what this package
does: it runs pylint, pyflakes, pycodestyle, mccabe, dodgy and pydocstyle together and
merges their output. The difference is what each aggregates. prospector aggregates
**findings** — "line 12 has a problem" — while this package aggregates **measurements** —
"this fragment has these values". Both are useful and they do not overlap.

What it contributes here is a single number for "how much does the assembled Python linting
ecosystem object to this code", plus the breakdown by which tool objected. On generated
code that is a response variable in its own right: models reproduce the idioms of their
training data, and how much a linter consortium dislikes the result is a measurable
property of the generator.

**prospector is GPL-2.0.** Like pylint, it is therefore reached only across a process
boundary and lives behind an optional extra, so that no copyleft code enters the import
tree ([ADR-0003](../../docs/adr/0003-mit-licence-and-copyleft-exclusion.md)). The licence
CI job asserts this.

Two practical notes. It is **slow** — several seconds per file, an order of magnitude more
than every other engine here — which is why it is off by default rather than merely
optional. And its findings are counted **by tool and by fixability**, never one column per
message code: prospector inherits pylint's hundreds of codes, and a column per code would
be a schema that breaks on every upstream release.
"""

from __future__ import annotations

import tempfile
from collections import Counter
from pathlib import Path

from ..contract import Adapter
from ..execution import responds, run, which
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

BINARY = "prospector"

_INVALID = NullSemantics.INVALID_INPUT

#: The tools prospector runs by default. Counted individually so that a change in its
#: default profile is visible as a column going quiet, rather than as a total shifting for
#: no apparent reason.
_TOOLS = ["pylint", "pyflakes", "pycodestyle", "mccabe", "dodgy", "profile-validator"]

_SPECS = [
    MetricSpec(
        key="prospector_messages",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Total findings from prospector's assembled linters. How much the Python "
            "linting ecosystem, taken together, objects to this code."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="prospector_fixable",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description="Findings prospector reports as automatically fixable.",
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="prospector_tools_reporting",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "How many distinct linters found something. Breadth of objection, as opposed "
            "to volume."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    *[
        MetricSpec(
            key=f"prospector_{tool.replace('-', '_')}",
            granularity=Granularity.FILE,
            unit="count",
            dtype="int",
            description=f"Findings attributed to {tool}.",
            valid_range=(0, None),
            null_semantics=_INVALID,
        )
        for tool in _TOOLS
    ],
]


class ProspectorAdapter(Adapter):
    name = "prospector"
    path = "subprocess"

    @property
    def version(self) -> str | None:
        binary = which(BINARY)
        if binary is None:
            return None
        result = run([binary, "--version"], timeout=60)
        if not result.ok:
            return None
        parts = result.stdout.strip().split()
        return parts[-1] if parts else None

    def is_available(self) -> bool:
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

        messages = report.get("messages") or []
        by_tool = Counter(m.get("source") for m in messages if isinstance(m, dict))

        values: dict[str, float | int | bool | None] = {
            "prospector_messages": len(messages),
            "prospector_fixable": sum(
                1 for m in messages if isinstance(m, dict) and m.get("isFixable")
            ),
            "prospector_tools_reporting": len([t for t, n in by_tool.items() if n]),
        }
        for tool in _TOOLS:
            values[f"prospector_{tool.replace('-', '_')}"] = by_tool.get(tool, 0)
        return AdapterResult(values=values, raw=report)

    def _run(self, binary: str, code: str) -> dict:
        with tempfile.TemporaryDirectory(prefix="dca-prospector-") as tmp:
            (Path(tmp) / "fragment.py").write_text(code, encoding="utf-8")
            result = run(
                [binary, "--output-format", "json", "--no-autodetect", "fragment.py"],
                cwd=tmp,
                timeout=180,  # prospector is an order of magnitude slower than the rest
            )
            if result.timed_out:
                raise TimeoutError("prospector exceeded the time budget analysing one fragment")
            if not result.stdout.strip():
                raise RuntimeError(
                    f"prospector exited {result.returncode} with no report: "
                    f"{result.stderr[:200]!r}"
                )
            return result.json()
