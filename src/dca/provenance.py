"""The provenance envelope — why no number here is ever emitted naked.

No tool in this domain stamps provenance. pyscn emits ``version`` and ``generated_at``,
which is the maximum found across the whole inventory; ast-metrics emits nothing; radon,
lizard, multimetric, wily and complexipy emit nothing.

The cost of that absence is measurable. radon's maintainability index saturates at exactly
100.0 for roughly a fifth of ordinary open-source Python, and **studies using radon do not
report what fraction of their dependent variable was a saturated constant** — because
nothing told them. A number without provenance is neither reproducible nor auditable.

Two rules make this work, and the second is the one that gets violated:

1. Every export carries the envelope.
2. **Versions are read from the running process**, never from dependency declarations
   (R-12). ``radon>=6.0.1`` is re-resolved at install time, so the declared pin and the
   installed version can differ; reporting the declaration would be a fabrication.

Every field degrades to None rather than raising. Provenance capture must never be able to
fail an export — an envelope with a missing hostname is useful; a failed run is not.
"""

from __future__ import annotations

import platform
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256 as _sha256
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _dist_version
from typing import Any

from .schema import SCHEMA_VERSION


def package_version() -> str | None:
    """This package's own installed version."""
    try:
        return _dist_version("deep-code-analysis")
    except PackageNotFoundError:
        return None


def _hostname_hash() -> str | None:
    """A stable, non-identifying host fingerprint.

    The hostname matters for reproducibility (did these two runs happen on the same
    machine?) but publishing it leaks institutional detail into a shared dataset. The
    hash answers the question without disclosing the answer.
    """
    try:
        return _sha256(platform.node().encode("utf-8")).hexdigest()[:16]
    except Exception:  # noqa: BLE001
        return None


@dataclass(slots=True)
class GenerationProvenance:
    """How the analysed code was produced, when it came from a model.

    Optional and caller-supplied: this package cannot observe it. It is what makes the
    envelope specifically useful for LLM research — a metric without the sampling
    parameters that produced its input is not a reproducible observation.
    """

    model: str | None = None
    temperature: float | None = None
    top_p: float | None = None
    top_k: int | None = None
    min_p: float | None = None
    seed: int | None = None
    repetition_penalty: float | None = None
    max_tokens: int | None = None
    prompt_sha256: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        base = {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
            "min_p": self.min_p,
            "seed": self.seed,
            "repetition_penalty": self.repetition_penalty,
            "max_tokens": self.max_tokens,
            "prompt_sha256": self.prompt_sha256,
        }
        base.update(self.extra)
        return base


@dataclass(slots=True)
class Provenance:
    """The full envelope for one analysis run."""

    run_id: str
    generated_at: str
    analysis_chain: dict[str, str | None]
    interpreter: dict[str, str | None]
    package: dict[str, str | None]
    environment: dict[str, str | None]
    embeddings: dict[str, dict[str, Any]] = field(default_factory=dict)
    inputs: dict[str, Any] = field(default_factory=dict)
    generation: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "analysis_chain": self.analysis_chain,
            "interpreter": self.interpreter,
            "package": self.package,
            "environment": self.environment,
            "inputs": self.inputs,
        }
        if self.embeddings:
            envelope["embeddings"] = self.embeddings
        # Omitted rather than nulled when absent: an absent block says "not model-generated
        # code", while a block of nulls says "model-generated, parameters unknown".
        if self.generation is not None:
            envelope["generation"] = self.generation
        return envelope


def _interpreter() -> dict[str, str | None]:
    return {
        # sys.version_info rather than platform.python_version(): this is the interpreter
        # whose `ast` grammar decides which fragments count as valid Python at all.
        "python_version": ".".join(str(p) for p in sys.version_info[:3]),
        "implementation": sys.implementation.name,
    }


def _environment() -> dict[str, str | None]:
    def safe(fn) -> str | None:
        try:
            return fn() or None
        except Exception:  # noqa: BLE001
            return None

    return {
        "os": safe(platform.system),
        "os_release": safe(platform.release),
        "arch": safe(platform.machine),
        "hostname_hash": _hostname_hash(),
    }


def build(
    adapters,
    *,
    run_id: str,
    fragment_count: int,
    embeddings: dict[str, dict[str, Any]] | None = None,
    generation: GenerationProvenance | None = None,
) -> Provenance:
    """Assemble the envelope for a run.

    ``adapters`` are the instances that actually ran, so the chain records what was used
    rather than what was available.
    """
    chain: dict[str, str | None] = {}
    for adapter in adapters:
        try:
            chain[adapter.name] = adapter.version
        except Exception:  # noqa: BLE001 - a broken version probe is not a failed run
            chain[adapter.name] = None

    return Provenance(
        run_id=run_id,
        generated_at=datetime.now(UTC).isoformat(),
        analysis_chain=chain,
        interpreter=_interpreter(),
        package={
            "name": "deep-code-analysis",
            "version": package_version(),
            "schema_version": SCHEMA_VERSION,
        },
        environment=_environment(),
        embeddings=embeddings or {},
        inputs={"fragment_count": fragment_count},
        generation=generation.as_dict() if generation is not None else None,
    )
