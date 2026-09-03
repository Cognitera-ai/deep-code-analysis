"""The adapter registry.

Order matters only for presentation: it is the order engines appear in the catalogue, in
``dca doctor``, and in the composed schema. Import-path engines come first because they are
always present; subprocess engines follow because they may not be.

The registry is the one place that knows every adapter. Adapters never import each other
(ADR-0012), so this module is also the only place a cycle could form, and it forms none:
it imports adapters, and no adapter imports it.
"""

from __future__ import annotations

from ..contract import Adapter
from .ast_adapter import AstAdapter
from .bandit_adapter import BanditAdapter
from .complexipy_adapter import ComplexipyAdapter
from .lexical_adapter import LexicalAdapter
from .lizard_adapter import LizardAdapter
from .prospector_adapter import ProspectorAdapter
from .pylint_adapter import PylintAdapter
from .pyscn_adapter import PyscnAdapter
from .radon_adapter import RadonAdapter
from .vulture_adapter import VultureAdapter

#: Engines that are part of the default analysis.
DEFAULT_ADAPTERS: list[type[Adapter]] = [
    RadonAdapter,
    LizardAdapter,
    AstAdapter,
    LexicalAdapter,
    ComplexipyAdapter,
    PyscnAdapter,
    VultureAdapter,
    BanditAdapter,
]

#: Engines behind an extra, off unless explicitly requested. pylint is here because of its
#: licence, not its quality (ADR-0011).
OPTIONAL_ADAPTERS: list[type[Adapter]] = [PylintAdapter, ProspectorAdapter]

ALL_ADAPTERS: list[type[Adapter]] = DEFAULT_ADAPTERS + OPTIONAL_ADAPTERS


def build(names: list[str] | None = None, *, include_optional: bool = False) -> list[Adapter]:
    """Instantiate adapters by name, or the default set.

    Unknown names raise: a typo in ``--engines`` should fail loudly rather than silently
    analysing with fewer engines than the caller asked for.
    """
    catalogue = {cls.name: cls for cls in ALL_ADAPTERS}
    if names is None:
        chosen = DEFAULT_ADAPTERS + (OPTIONAL_ADAPTERS if include_optional else [])
        return [cls() for cls in chosen]
    unknown = [n for n in names if n not in catalogue]
    if unknown:
        raise ValueError(
            f"unknown engine(s): {', '.join(sorted(unknown))}. "
            f"Available: {', '.join(sorted(catalogue))}"
        )
    return [catalogue[n]() for n in names]


__all__ = [
    "Adapter", "AstAdapter", "BanditAdapter", "ComplexipyAdapter", "LexicalAdapter",
    "LizardAdapter",
    "ProspectorAdapter", "PylintAdapter", "PyscnAdapter", "RadonAdapter", "VultureAdapter",
    "DEFAULT_ADAPTERS", "OPTIONAL_ADAPTERS", "ALL_ADAPTERS", "build",
]
