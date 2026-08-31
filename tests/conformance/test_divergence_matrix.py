"""The divergence matrix over the minimal corpus.

This is deliverable 2 of the conformance suite (spec §9.2): for every metric more than one
engine computes, how often they disagreed and by how much. It is the table that would go in
a paper, and running it in CI means the numbers in that paper cannot silently rot.
"""

from __future__ import annotations

from dca.core import Analyser


def test_divergence_matrix_is_produced(corpus):
    """A-06. The matrix must exist, name its metrics, and be non-trivial."""
    frame = Analyser().analyse_many(corpus)
    summary = frame.divergence_summary()

    assert not summary.empty
    assert {"metric", "compared", "divergent", "divergent_rate"} <= set(summary.columns)

    metrics = set(summary["metric"])
    assert "halstead_volume" in metrics
    assert "cyclomatic_complexity_mean" in metrics


def test_halstead_diverges_and_cyclomatic_does_not(corpus):
    """The calibration that keeps the package's claims honest.

    Halstead is where the engines break down. Cyclomatic complexity is where they agree —
    radon and lizard match exactly on 99.2 % of a real corpus, differing by at most one.
    A package claiming everything is broken would be as useless as one claiming nothing is.
    """
    frame = Analyser(engines=["radon", "lizard"]).analyse_many(corpus)
    summary = frame.divergence_summary().set_index("metric")

    halstead = summary.loc["halstead_volume"]
    assert halstead["divergent_rate"] > 0.5

    cyclomatic = summary.loc["cyclomatic_complexity_max"]
    assert cyclomatic["divergent_rate"] < 0.5


def test_null_rates_are_reported(corpus):
    """The null rate per column is a research datum, not a diagnostic afterthought: it is
    exactly what revealed that radon's MI was a constant for three quarters of a corpus."""
    frame = Analyser().analyse_many(corpus)
    rates = frame.null_rates()

    assert not rates.empty
    assert (rates <= 1.0).all() and (rates >= 0.0).all()
    # lizard cannot measure flat scripts, and the corpus has several.
    assert rates["halstead_volume__lizard"] > 0
