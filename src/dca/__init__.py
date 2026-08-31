"""deep-code-analysis — structural measurement of Python code with verifiable provenance.

Quick start::

    from dca import analyse, analyse_many

    result = analyse(source)
    result.value("halstead_volume", "radon")     # radon's reading
    result.value("halstead_volume", "lizard")    # lizard's reading, often very different
    result.provenance                            # what produced both

    frame = analyse_many(fragments)
    frame.divergence_summary()                   # where the engines disagreed
    frame.to_parquet("out/")

What makes this package different from wrapping radon in a DataFrame:

* **No canonical engine.** Every metric more than one engine computes is emitted once per
  engine, plus their ratio and a divergence flag. radon and lizard differ by a median factor
  of 14 on Halstead volume over ordinary open-source Python; picking one would hide that,
  and averaging would invent a number true under no definition.
* **No naked numbers.** Every value carries the engine that produced it, and every run
  carries an envelope recording versions, interpreter and environment. No other tool in the
  domain does this, which is why published studies using radon cannot report what share of
  their dependent variable was a saturated constant.
* **Nothing reimplemented.** Every metric comes from its reference engine, so "how do I know
  this is right?" is answered by a version number rather than by trust.
"""

from __future__ import annotations

from .core import Analyser, FragmentResult, analyse, analyse_many, comparable_keys, divergence
from .frame import MetricFrame
from .history import measure as measure_history
from .history import revisions, trend
from .provenance import GenerationProvenance, Provenance
from .schema import SCHEMA_VERSION, Degradation, Granularity, MetricSpec, NullSemantics

__version__ = "0.1.0"

__all__ = [
    "Analyser",
    "Degradation",
    "FragmentResult",
    "GenerationProvenance",
    "Granularity",
    "MetricFrame",
    "measure_history",
    "revisions",
    "trend",
    "MetricSpec",
    "NullSemantics",
    "Provenance",
    "SCHEMA_VERSION",
    "__version__",
    "analyse",
    "analyse_many",
    "comparable_keys",
    "divergence",
]
