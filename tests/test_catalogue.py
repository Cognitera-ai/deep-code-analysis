"""The generated metric catalogue."""

from __future__ import annotations

from dca.adapters import build
from dca.catalogue import generate


def test_catalogue_documents_every_column():
    """R-16: the catalogue is generated from the same declarations the schema is built
    from, so it cannot drift."""
    adapters = build(None, include_optional=True)
    text = generate(adapters)

    for adapter in adapters:
        for spec in adapter.declared_metrics:
            assert f"`{spec.key}__{adapter.name}`" in text, f"{spec.key} undocumented"
            assert spec.description in text


def test_catalogue_marks_itself_as_generated():
    """A hand-edited generated file is a file that will silently disagree with the code."""
    text = generate(build(["radon"]))
    assert "do not edit by hand" in text.lower()


def test_catalogue_explains_the_divergence_columns():
    text = generate(build(["radon", "lizard"]))

    assert "halstead_volume__delta_ratio" in text
    assert "halstead_volume__divergent" in text
    assert "strongest disagreement" in text
