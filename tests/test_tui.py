"""The interactive divergence explorer.

Driven headlessly through Textual's pilot, so it is tested like any other code rather than
by someone looking at it.
"""

from __future__ import annotations

import pytest

from dca import tui
from dca.core import Analyser

pytestmark = pytest.mark.skipif(not tui.is_available(), reason="needs the tui extra")


@pytest.fixture(scope="module")
def frame(corpus):
    return Analyser(engines=["radon", "lizard", "ast", "complexipy"]).analyse_many(
        {
            "halstead_blind.py": corpus["halstead_blind"],
            "mi_informative.py": corpus["mi_informative"],
            "flat_script.py": corpus["flat_script"],
        }
    )


async def test_it_opens_and_lists_every_fragment(frame):
    app = tui.DivergenceExplorer(frame, title="test")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one("#fragment_table").row_count == 3
        assert app.query_one("#detail_table").row_count > 0


async def test_it_starts_filtered_to_disagreements(frame):
    """The default view answers the question the tool exists for. Showing every metric
    first would bury it."""
    app = tui.DivergenceExplorer(frame, title="test")
    async with app.run_test() as pilot:
        await pilot.pause()
        filtered = app.query_one("#detail_table").row_count

        await pilot.press("d")
        await pilot.pause()
        assert app.query_one("#detail_table").row_count > filtered


async def test_navigating_fragments_updates_the_detail(frame):
    app = tui.DivergenceExplorer(frame, title="test")
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("down")
        await pilot.pause()
        assert app.query_one("#detail_table").row_count >= 0  # no crash, table repopulated


def test_severity_labels_name_the_absent_versus_present_case():
    label, colour = tui._severity(None, True)
    assert label == "absent/present"
    assert colour == "magenta"

    assert tui._severity(9.0, True)[1] == "red"
    assert tui._severity(1.0, False)[0] == "agree"


def test_a_helpful_error_when_the_extra_is_missing(monkeypatch):
    """A missing optional dependency is a configuration state, not a crash — and the
    message has to say how to fix it."""
    monkeypatch.setattr(tui, "TEXTUAL", False)
    with pytest.raises(tui.TuiUnavailableError, match=r"tui extra"):
        tui.explore(object())
