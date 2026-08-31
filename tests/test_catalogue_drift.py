"""The committed catalogue must match what the code generates (R-16).

An out-of-date catalogue is a build failure, not a chore. The alternative — a document that
quietly disagrees with the schema — is worse than having no document, because it is trusted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dca.adapters import build
from dca.catalogue import generate

CATALOGUE = Path(__file__).resolve().parent.parent / "docs" / "metric-catalogue.md"


def test_committed_catalogue_is_current():
    if not CATALOGUE.exists():
        pytest.fail(
            "docs/metric-catalogue.md is missing; run: "
            "dca catalogue --write docs/metric-catalogue.md"
        )

    committed = CATALOGUE.read_text(encoding="utf-8")
    generated = generate(build(None, include_optional=True))

    if committed != generated:
        pytest.fail(
            "docs/metric-catalogue.md is out of date.\n"
            "Regenerate with: dca catalogue --write docs/metric-catalogue.md"
        )
