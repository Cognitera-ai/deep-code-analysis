"""The adapter contract — the single boundary every engine is integrated behind.

Seven heterogeneous engines produce everything from Python objects to subprocess JSON, at
file, function and class granularity. Without one boundary each of them imposes its shape
on the core, and the package becomes unmaintainable — which is how aggregators in this
domain die (ADR-0012).

Four rules, all enforceable and all enforced by ``tests/test_contract.py``:

1. No adapter writes to the schema. It returns its vector; the core composes.
2. No adapter imports another adapter. Divergence is a core concern (R-08).
3. The engine name goes in the column name, always (R-03).
4. A broken engine is disabled without touching the rest — ``is_available()`` returning
   False produces null columns, not a crash.

Rule 1 is what makes the adapters parallelisable: whoever writes the bandit adapter never
needs to know what the radon adapter does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from typing import Literal

from .schema import AdapterResult, Degradation, MetricSpec

AdapterPath = Literal["import", "subprocess"]


class Adapter(ABC):
    """Base class for every engine integration."""

    #: Engine identity. Goes verbatim into every column this adapter produces, so it must
    #: be short, stable, and a valid identifier fragment.
    name: str
    #: How the engine is reached. Copyleft engines may only ever be "subprocess"
    #: (ADR-0003); the licence CI job checks this.
    path: AdapterPath = "import"
    #: Distribution name for version resolution, when it differs from ``name``.
    distribution: str | None = None

    @property
    def version(self) -> str | None:
        """Version of the engine **as installed in the running process** (R-12).

        Deliberately not read from ``pyproject.toml``: a floor specifier like
        ``lizard>=1.24.0`` is re-resolved at install time, so the declared pin and the
        installed version can differ, and reporting the declaration would be a
        fabrication. Subprocess adapters override this to ask their binary.
        """
        try:
            return _dist_version(self.distribution or self.name)
        except PackageNotFoundError:
            return None

    @abstractmethod
    def is_available(self) -> bool:
        """Whether this engine can run here and now. Must never raise."""

    @property
    @abstractmethod
    def declared_metrics(self) -> list[MetricSpec]:
        """Every metric key this adapter promises to emit.

        The generated catalogue is built from this (R-16), and the schema is assembled
        from it, so an adapter that emits a key it did not declare will have that key
        dropped — loudly, in the contract tests.
        """

    @abstractmethod
    def analyse(self, code: str) -> AdapterResult:
        """Measure one fragment. Must never raise (R-19).

        Any failure is returned as a :class:`Degradation` inside the result, so that one
        pathological fragment degrades to nulls instead of aborting a batch of thousands
        (ADR-0013).
        """

    # ── helpers available to every adapter ──────────────────────────────────────────

    def _null_result(self, keys: list[str] | None = None) -> AdapterResult:
        """A result with every declared metric null. The shape of "did not measure"."""
        wanted = keys if keys is not None else [m.key for m in self.declared_metrics]
        return AdapterResult(values=dict.fromkeys(wanted))

    def _degraded(
        self, fragment_id: str, exc: BaseException, kind: str = "engine_error"
    ) -> AdapterResult:
        """A null result carrying the reason it is null (R-20)."""
        result = self._null_result()
        result.failures.append(
            Degradation(
                engine=self.name,
                fragment_id=fragment_id,
                kind=kind,
                detail=f"{type(exc).__name__}: {exc}",
            )
        )
        return result

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<{type(self).__name__} name={self.name!r} version={self.version!r}>"


def aggregate(values: list[float | int], prefix: str) -> dict[str, float | None]:
    """Aggregate a per-function series to the fragment as mean/max/min (R-07).

    One row per fragment is the schema contract, so anything measured per function has to
    collapse. The collapse is lossy, which is why the per-function detail is also exposed
    through :meth:`AdapterResult.functions` and the ``functions`` table.

    An empty series yields nulls, never zeros: "this fragment defines no functions" is an
    absence, not a measurement of zero (R-05).
    """
    if not values:
        return {f"{prefix}_mean": None, f"{prefix}_max": None, f"{prefix}_min": None}
    return {
        f"{prefix}_mean": round(sum(values) / len(values), 4),
        f"{prefix}_max": max(values),
        f"{prefix}_min": min(values),
    }
