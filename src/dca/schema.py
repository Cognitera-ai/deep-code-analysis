"""Schema definitions: metric specs, column naming, and the schema version.

The schema is the package's contract with its consumers. Three rules from the spec are
enforced here rather than by convention, because every one of them has been violated by a
well-meaning implementation before:

* **The bare metric name is forbidden** (R-03). Every column carries the engine that
  produced it, so a reader can never assume there is one answer to "what is the Halstead
  volume of this code" when there demonstrably is not (ADR-0004).
* **The scalar schema is fixed, not conditional** (R-13). An engine that did not run
  produces null columns, never absent ones, so frames from different runs concatenate.
* **Null is not zero** (R-05). Zero is a measurement; null is an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

# Semantic and independent of the package version (R-15). Consumers pin against this.
# Adding a column is a minor bump; renaming or removing one is a major bump.
SCHEMA_VERSION = "1.0.0"

#: Separator between a metric key and the engine that produced it. The double underscore
#: is deliberate: single underscores appear inside metric keys (``halstead_volume``), so a
#: single separator could not be parsed back apart.
ENGINE_SEP = "__"

#: Suffix for the ratio between two engines' readings of the same metric (R-08).
DELTA_RATIO_SUFFIX = "delta_ratio"
#: Suffix for the boolean flag raised when that ratio crosses the threshold (R-09).
DIVERGENT_SUFFIX = "divergent"

#: Relative difference above which two engines are called divergent (R-09). Arbitrary but
#: documented and configurable — it is a reporting threshold, not a finding.
DEFAULT_DIVERGENCE_THRESHOLD = 0.10


class Granularity(StrEnum):
    """The level a metric is natively measured at.

    Anything below ``FILE`` has to be aggregated to reach the one-row-per-fragment schema
    (R-07), and the aggregation is lossy, which is why the per-function detail is also
    exposed separately.
    """

    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"


class NullSemantics(StrEnum):
    """What a null in this column means.

    This distinction is not decoration. A ``loop_ratio`` of zero means the code genuinely
    has no loops — a measurement. A ``halstead_difficulty`` of zero usually means radon
    recognised none of the operators that are present — an absence wearing a measurement's
    clothes. Treating those two as the same kind of zero is how an instrument artefact gets
    reported as a finding.
    """

    #: The metric does not apply to this fragment (no classes, so no cohesion).
    NOT_APPLICABLE = "not_applicable"
    #: The engine failed or was unavailable.
    UNMEASURED = "unmeasured"
    #: The fragment is not valid Python, so nothing static can be read off it.
    INVALID_INPUT = "invalid_input"


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One metric an adapter promises to emit.

    This is the unit the generated catalogue is built from (R-16), so every field here
    ends up in user-facing documentation. A metric without a description is a metric
    nobody can use.
    """

    key: str
    granularity: Granularity
    unit: str
    dtype: Literal["int", "float", "bool"]
    description: str
    valid_range: tuple[float | None, float | None] = (None, None)
    null_semantics: NullSemantics = NullSemantics.UNMEASURED
    #: True when more than one engine emits this key, so the core should compute the
    #: divergence pair for it (R-08). Set by the core, not by adapters.
    comparable: bool = False

    def column(self, engine: str) -> str:
        """The schema column name for this metric as produced by ``engine`` (R-03)."""
        return column_name(self.key, engine)


def column_name(key: str, engine: str) -> str:
    """Compose a schema column name. The only sanctioned way to name a metric column."""
    if not engine:
        raise ValueError(
            f"metric {key!r} was given an empty engine name; the bare metric name is "
            "forbidden in the schema (R-03)"
        )
    return f"{key}{ENGINE_SEP}{engine}"


def split_column(column: str) -> tuple[str, str | None]:
    """Inverse of :func:`column_name`. Returns ``(key, engine)``; engine is None if absent."""
    if ENGINE_SEP not in column:
        return column, None
    key, _, engine = column.rpartition(ENGINE_SEP)
    return key, engine


def is_true(value: object) -> bool:
    """Whether a schema flag is set, safely across a round trip through pandas.

    ``value is True`` is the obvious spelling and it is wrong here. A boolean read back
    from a DataFrame is a ``numpy.bool_``, which since NumPy 2 even reports its type name
    as ``"bool"`` — it prints as ``True``, compares equal to ``True``, and fails ``is
    True``. The identity check therefore silently reports every divergence flag as unset,
    with nothing looking broken.

    That is exactly what happened: the CLI overview showed zero disagreements on a fragment
    where radon reported 0 and lizard reported 139, and it was only caught by looking at a
    rendered screenshot.

    Nulls are excluded deliberately: a flag is null when there was nothing to compare, and
    that is not the same as compared-and-agreed.
    """
    if value is None:
        return False
    try:
        return bool(value)
    except (TypeError, ValueError):  # pragma: no cover - a value that cannot be truthed
        return False


def delta_column(key: str) -> str:
    """Column holding the inter-engine ratio for ``key``."""
    return f"{key}{ENGINE_SEP}{DELTA_RATIO_SUFFIX}"


def divergent_column(key: str) -> str:
    """Column holding the divergence flag for ``key``."""
    return f"{key}{ENGINE_SEP}{DIVERGENT_SUFFIX}"


# ── Identity columns (§6.2) ──────────────────────────────────────────────────────────
#
# `language` is always "python" in v1 and exists only so that adding a language later is a
# minor schema bump rather than a breaking one (ADR-0002).

IDENTITY_COLUMNS = ["fragment_id", "code_sha256", "is_valid_python", "language"]

DEFAULT_LANGUAGE = "python"


@dataclass(frozen=True, slots=True)
class Degradation:
    """One recorded failure that was degraded rather than raised (R-20).

    A silent degradation is a defect: a broken engine that quietly emits nulls looks
    exactly like a corpus where the metric does not apply. The degradation table is what
    separates those two cases after the fact.
    """

    engine: str
    fragment_id: str
    kind: str
    detail: str

    def as_row(self) -> dict[str, str]:
        return {
            "engine": self.engine,
            "fragment_id": self.fragment_id,
            "kind": self.kind,
            "detail": self.detail,
        }


@dataclass(slots=True)
class AdapterResult:
    """What every adapter returns. Never an exception (R-19)."""

    #: Metric key (not column name) to value. The core adds the engine suffix, so an
    #: adapter cannot accidentally claim a column that is not its own.
    values: dict[str, float | int | bool | None] = field(default_factory=dict)
    #: Per-function rows, for adapters whose native granularity is below file level.
    functions: list[dict[str, float | int | str | None]] = field(default_factory=list)
    failures: list[Degradation] = field(default_factory=list)
    #: Engine-native output, kept only for the conformance suite. Never written to the
    #: schema — it is unnormalised by definition.
    raw: object | None = None

    @property
    def ok(self) -> bool:
        return not self.failures
