"""Shared fixtures.

Tests run against **real engine output**, never mocks (R-24). Mocking an engine's response
would hide exactly the class of bug this package exists to find: that engines disagree, and
that one of them returns a saturated constant on a large share of realistic input. A test
suite that mocked radon would pass while the package reported nonsense.
"""

from __future__ import annotations

from pathlib import Path

import pytest

CORPUS = Path(__file__).parent / "conformance" / "corpus" / "minimal"


def _load(name: str) -> str:
    return (CORPUS / name).read_text(encoding="utf-8")


@pytest.fixture(scope="session")
def corpus() -> dict[str, str]:
    """The whole minimal corpus, keyed by filename stem.

    Includes the two ``.py.txt`` files, which are not valid Python on purpose.
    """
    fragments = {}
    for path in sorted(CORPUS.iterdir()):
        if path.name == "README.md":
            continue
        key = path.name.replace(".py.txt", "").replace(".py", "")
        fragments[key] = path.read_text(encoding="utf-8")
    return fragments


@pytest.fixture(scope="session")
def halstead_blind() -> str:
    """Valid Python that radon sees no operators in. The founding observation."""
    return _load("halstead_blind.py")


@pytest.fixture(scope="session")
def flat_script() -> str:
    """No function definitions: drives CC imputation and lizard's nulls."""
    return _load("flat_script.py")


@pytest.fixture(scope="session")
def mi_informative() -> str:
    """Arithmetic-heavy, so the maintainability index is actually computed."""
    return _load("mi_informative.py")


@pytest.fixture(scope="session")
def with_classes() -> str:
    """Has classes, so the OO metrics are non-null."""
    return _load("with_classes.py")


@pytest.fixture(scope="session")
def invalid_code() -> str:
    return _load("invalid_syntax.py.txt")


@pytest.fixture(scope="session")
def analyser():
    """One analyser for the session: probing subprocess engines costs a process spawn."""
    from dca.core import Analyser

    return Analyser()
