"""Schema composition — where the adapters' vectors become one table.

This module owns the three things no adapter is allowed to do:

* **Naming columns.** Every metric column is ``{key}__{engine}`` (R-03). Adapters return
  bare metric keys and never see a column name, which is what makes it impossible for one
  to claim a column belonging to another.
* **Computing divergence.** When more than one engine emits a key, the core emits every
  engine's reading plus the ratio between them and a flag (R-08, ADR-0004). Adapters do not
  import each other, so only the core is in a position to compare.
* **Holding the schema fixed.** An engine that did not run yields null columns, never
  absent ones (R-13), so frames from different runs concatenate without alignment games.

The divergence machinery is the point of the package. radon and lizard disagree about
Halstead volume by a median factor of 14 on ordinary open-source Python; complexipy and
pyscn disagree about cognitive complexity. Averaging those would invent a number that is true
under no definition, and picking one would hide the disagreement. Reporting both, with the
ratio, turns the problem into the measurement.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .adapters import build as build_adapters
from .contract import Adapter
from .parsing import is_valid_python, sha256
from .provenance import GenerationProvenance, Provenance
from .provenance import build as build_provenance
from .schema import (
    DEFAULT_DIVERGENCE_THRESHOLD,
    DEFAULT_LANGUAGE,
    Degradation,
    MetricSpec,
    column_name,
    delta_column,
    divergent_column,
)

if TYPE_CHECKING:  # pragma: no cover - import cycle: frame imports core for FragmentResult
    from .frame import MetricFrame

Number = float | int | bool | None


def comparable_keys(adapters: Sequence[Adapter]) -> dict[str, list[str]]:
    """Metric keys emitted by more than one engine, mapped to those engines.

    Derived from the adapters' declarations rather than hard-coded, so adding an engine
    that happens to emit ``halstead_volume`` automatically brings it into the comparison
    without anyone remembering to update a list.
    """
    by_key: dict[str, list[str]] = defaultdict(list)
    for adapter in adapters:
        for spec in adapter.declared_metrics:
            by_key[spec.key].append(adapter.name)
    return {key: engines for key, engines in by_key.items() if len(engines) > 1}


def divergence(
    readings: dict[str, Number], threshold: float = DEFAULT_DIVERGENCE_THRESHOLD
) -> tuple[float | None, bool | None]:
    """Compare several engines' readings of one metric.

    Returns ``(ratio, divergent)`` where ratio is largest over smallest.

    Three cases deserve their own treatment, and conflating them is how a real
    disagreement gets reported as agreement:

    * **Fewer than two readings.** Nothing to compare: ``(None, None)``. Not "they agree".
    * **All readings zero.** Ratio is undefined (0/0), but the engines *do* agree:
      ``(None, False)``.
    * **Some zero, some not.** This is the strongest possible disagreement — one engine
      says the quantity is absent, another says it is present — and a ratio cannot express
      it. Flagged divergent with no ratio. This is exactly the radon/lizard Halstead case
      on flat-ish code, and it is the single most informative signal the package emits.
    """
    values = [float(v) for v in readings.values() if v is not None]
    if len(values) < 2:
        return None, None

    zeros = [v for v in values if v == 0]
    non_zeros = [v for v in values if v != 0]
    if not non_zeros:
        return None, False
    if zeros:
        return None, True

    low, high = min(non_zeros), max(non_zeros)
    ratio = round(high / low, 6)
    return ratio, (ratio - 1.0) > threshold


@dataclass(slots=True)
class FragmentResult:
    """Everything measured about one fragment.

    A typed object rather than a bare dict (R-17): the provenance travels with the numbers,
    so it is not possible to hold a metric value in your hand without also holding the
    record of what produced it.
    """

    fragment_id: str
    code_sha256: str
    is_valid_python: bool
    language: str
    metrics: dict[str, Number]
    functions: list[dict[str, Any]] = field(default_factory=list)
    degradations: list[Degradation] = field(default_factory=list)
    provenance: Provenance | None = None

    def identity(self) -> dict[str, Any]:
        return {
            "fragment_id": self.fragment_id,
            "code_sha256": self.code_sha256,
            "is_valid_python": self.is_valid_python,
            "language": self.language,
        }

    def as_row(self) -> dict[str, Any]:
        """One flat row: identity columns first, then metrics in schema order."""
        return {**self.identity(), **self.metrics}

    def value(self, key: str, engine: str) -> Number:
        """Read one engine's reading of one metric, by name rather than by column."""
        return self.metrics.get(column_name(key, engine))


class Analyser:
    """Runs a set of adapters over fragments and composes their output.

    Holding this as an object rather than a function matters for batches: engine
    availability and version are probed once, not once per fragment, and probing a
    subprocess engine's version costs a process spawn.
    """

    def __init__(
        self,
        adapters: Sequence[Adapter] | None = None,
        *,
        engines: list[str] | None = None,
        include_optional: bool = False,
        divergence_threshold: float = DEFAULT_DIVERGENCE_THRESHOLD,
    ) -> None:
        self.adapters: list[Adapter] = (
            list(adapters)
            if adapters is not None
            else build_adapters(engines, include_optional=include_optional)
        )
        self.divergence_threshold = divergence_threshold
        self._available = {a.name: a.is_available() for a in self.adapters}
        self._comparable = comparable_keys(self.adapters)

    # ── schema ──────────────────────────────────────────────────────────────────────

    @property
    def specs(self) -> list[tuple[str, MetricSpec]]:
        """``(engine, spec)`` for every metric in the schema, in engine order."""
        return [(a.name, spec) for a in self.adapters for spec in a.declared_metrics]

    def columns(self) -> list[str]:
        """Every metric column, in schema order. Fixed regardless of what ran (R-13)."""
        names = [column_name(spec.key, engine) for engine, spec in self.specs]
        for key in sorted(self._comparable):
            names.append(delta_column(key))
            names.append(divergent_column(key))
        return names

    def available_engines(self) -> dict[str, bool]:
        return dict(self._available)

    # ── analysis ────────────────────────────────────────────────────────────────────

    def analyse(self, code: str, *, fragment_id: str | None = None) -> FragmentResult:
        """Measure one fragment with every configured engine."""
        fid = fragment_id or str(uuid.uuid4())
        valid = is_valid_python(code)

        metrics: dict[str, Number] = {}
        functions: list[dict[str, Any]] = []
        degradations: list[Degradation] = []
        per_key: dict[str, dict[str, Number]] = defaultdict(dict)

        for adapter in self.adapters:
            declared = [spec.key for spec in adapter.declared_metrics]
            if not self._available.get(adapter.name, False):
                # An unavailable engine yields nulls for its whole block, not an error and
                # not absent columns.
                result_values: dict[str, Number] = dict.fromkeys(declared)
                result_functions: list[dict[str, Any]] = []
            else:
                result = adapter.analyse(code)
                # An adapter emitting a key it did not declare would silently widen the
                # schema, so undeclared keys are dropped here and surfaced by the contract
                # tests rather than reaching a consumer.
                result_values = {k: result.values.get(k) for k in declared}
                result_functions = result.functions
                for failure in result.failures:
                    degradations.append(
                        Degradation(
                            engine=failure.engine,
                            fragment_id=fid,
                            kind=failure.kind,
                            detail=failure.detail,
                        )
                    )

            for key, value in result_values.items():
                metrics[column_name(key, adapter.name)] = value
                if key in self._comparable:
                    per_key[key][adapter.name] = value

            for row in result_functions:
                functions.append({"fragment_id": fid, "engine": adapter.name, **row})

        for key in sorted(self._comparable):
            ratio, divergent = divergence(per_key.get(key, {}), self.divergence_threshold)
            metrics[delta_column(key)] = ratio
            metrics[divergent_column(key)] = divergent

        return FragmentResult(
            fragment_id=fid,
            code_sha256=sha256(code),
            is_valid_python=valid,
            language=DEFAULT_LANGUAGE,
            metrics=metrics,
            functions=functions,
            degradations=degradations,
        )

    def analyse_many(
        self,
        fragments: Iterable[str] | dict[str, str],
        *,
        generation: GenerationProvenance | None = None,
    ) -> MetricFrame:
        """Measure a batch, returning a frame with one row per fragment.

        A dict maps caller-supplied ids to code; an iterable gets generated ids.
        """
        from .frame import MetricFrame

        if isinstance(fragments, dict):
            items = list(fragments.items())
        else:
            items = [(str(uuid.uuid4()), code) for code in fragments]

        results = [self.analyse(code, fragment_id=fid) for fid, code in items]
        provenance = build_provenance(
            self.adapters,
            run_id=str(uuid.uuid4()),
            fragment_count=len(results),
            generation=generation,
        )
        for result in results:
            result.provenance = provenance
        return MetricFrame(results, provenance=provenance, columns=self.columns())


def analyse(
    code: str,
    *,
    engines: list[str] | None = None,
    include_optional: bool = False,
    generation: GenerationProvenance | None = None,
) -> FragmentResult:
    """Measure one fragment. The package's front door.

    For more than a handful of fragments use :func:`analyse_many`, which probes engine
    availability once instead of once per call.
    """
    analyser = Analyser(engines=engines, include_optional=include_optional)
    result = analyser.analyse(code)
    result.provenance = build_provenance(
        analyser.adapters,
        run_id=str(uuid.uuid4()),
        fragment_count=1,
        generation=generation,
    )
    return result


def analyse_many(
    fragments: Iterable[str] | dict[str, str],
    *,
    engines: list[str] | None = None,
    include_optional: bool = False,
    generation: GenerationProvenance | None = None,
) -> MetricFrame:
    """Measure a batch of fragments into one frame."""
    analyser = Analyser(engines=engines, include_optional=include_optional)
    return analyser.analyse_many(fragments, generation=generation)
