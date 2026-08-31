"""The divergence machinery — the package's reason for existing."""

from __future__ import annotations

from dca.adapters import build
from dca.core import comparable_keys, divergence


def test_fewer_than_two_readings_is_not_agreement():
    """One engine cannot agree with itself; the answer is 'unknown', not 'no divergence'."""
    assert divergence({}) == (None, None)
    assert divergence({"radon": 5.0}) == (None, None)
    assert divergence({"radon": 5.0, "lizard": None}) == (None, None)


def test_all_zero_is_agreement_without_a_ratio():
    """0/0 has no ratio, but the engines do agree that the quantity is absent."""
    ratio, divergent = divergence({"radon": 0, "lizard": 0})
    assert ratio is None
    assert divergent is False


def test_zero_versus_non_zero_is_the_strongest_disagreement():
    """One engine says absent, another says present. No ratio can express that."""
    ratio, divergent = divergence({"radon": 0.0, "lizard": 139.0})
    assert ratio is None
    assert divergent is True


def test_ratio_is_largest_over_smallest():
    ratio, divergent = divergence({"radon": 4.75, "lizard": 47.5})
    assert ratio == 10.0
    assert divergent is True


def test_close_readings_are_not_flagged():
    ratio, divergent = divergence({"radon": 100.0, "lizard": 105.0})
    assert ratio == 1.05
    assert divergent is False


def test_threshold_is_configurable():
    assert divergence({"a": 100.0, "b": 105.0}, threshold=0.01)[1] is True
    assert divergence({"a": 100.0, "b": 105.0}, threshold=0.50)[1] is False


def test_comparable_keys_are_derived_not_hard_coded():
    """Adding an engine that emits an existing key must bring it into the comparison
    automatically, without anyone updating a list."""
    adapters = build(["radon", "lizard"])
    comparable = comparable_keys(adapters)
    assert "halstead_volume" in comparable
    assert set(comparable["halstead_volume"]) == {"radon", "lizard"}
    # radon alone compares with nobody.
    assert comparable_keys(build(["radon"])) == {}
