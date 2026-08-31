"""Bounded subprocess execution.

These test the guarantees that keep a batch alive, each of which comes from a real incident
(ADR-0013).
"""

from __future__ import annotations

import sys

from dca.execution import MAX_OUTPUT_BYTES, run, which


def test_captures_normal_output():
    result = run([sys.executable, "-c", "print('hello')"])
    assert result.ok
    assert result.stdout.strip() == "hello"


def test_non_zero_exit_is_an_outcome_not_an_exception():
    """Analysis tools exit non-zero to mean 'I found something'. That is data."""
    result = run([sys.executable, "-c", "import sys; sys.exit(3)"])
    assert result.returncode == 3
    assert not result.ok


def test_timeout_kills_the_child():
    result = run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=1)
    assert result.timed_out
    assert not result.ok


def test_unbounded_output_is_capped_without_hanging():
    """R-11, the incident that caused an OOM kill.

    The child prints far more than the cap. We must keep at most the cap, must not run out
    of memory, and must not report a timeout — the child exits cleanly and only appears to
    hang if the parent stops reading.
    """
    program = "print('x' * 1000000)\n" * 30  # ~30 MB, three times the cap
    result = run([sys.executable, "-c", program], timeout=60)

    assert not result.timed_out, "draining stopped early and the child blocked on a full pipe"
    assert result.truncated
    assert len(result.stdout.encode()) <= MAX_OUTPUT_BYTES + 100


def test_a_child_that_prints_a_lot_then_exits_is_not_a_timeout():
    """The specific misreport the drain-past-the-cap rule prevents."""
    program = "print('y' * 500000)\n" * 40 + "print('done')"
    result = run([sys.executable, "-c", program], timeout=60)

    assert not result.timed_out
    assert result.returncode == 0


def test_which_finds_binaries_beside_the_interpreter():
    """Engines installed into the same virtualenv must be discoverable even when that
    environment is not activated."""
    assert which("python") or which("python3")
    assert which("definitely-not-a-real-binary-xyz") is None
