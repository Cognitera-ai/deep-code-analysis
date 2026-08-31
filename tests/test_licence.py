"""The licence boundary, checked rather than trusted.

ADR-0003 forbids copyleft packages in the import tree, because importing one would with
high probability force this package to be copyleft too — which would prevent its use inside
other academic artifacts under different licences.

The rule is easy to state and easy to break by accident: `import pylint` is one keystroke
away from `subprocess.run(["pylint", ...])`, and it looks tidier. So it is a test, and in
CI it is a job.
"""

from __future__ import annotations

import re
from importlib.metadata import metadata
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "dca"

#: Packages that must never appear in an import statement. Each is copyleft; where one is
#: used at all, it is reached as a subprocess.
FORBIDDEN_IMPORTS = ["pylint", "cohesion", "prospector", "astroid"]

#: Licence identifiers that would contaminate a permissive package. Matched on word
#: boundaries, not as substrings: "MPL" is a substring of "IMPLEMENTATION", which appears
#: in every package's Programming Language classifiers.
COPYLEFT_MARKERS = ("GPL", "AGPL", "EUPL", "MPL", "CDDL", "EPL")

#: Everything on the import path (§2.1 of the spec), which must be permissive.
IMPORT_PATH_PACKAGES = ["radon", "lizard", "complexipy", "pandas", "numpy", "pyarrow"]


def _python_sources() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


@pytest.mark.parametrize("forbidden", FORBIDDEN_IMPORTS)
def test_no_copyleft_package_is_imported(forbidden: str):
    for path in _python_sources():
        source = path.read_text(encoding="utf-8")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert not stripped.startswith(f"import {forbidden}"), f"{path.name}: {stripped}"
            assert not stripped.startswith(f"from {forbidden}"), f"{path.name}: {stripped}"


@pytest.mark.parametrize("package", IMPORT_PATH_PACKAGES)
def test_import_path_dependencies_are_permissive(package: str):
    """Every dependency we import must be permissively licensed.

    Only licence-bearing fields are inspected. Scanning all metadata would flag
    "IMPLEMENTATION" for containing "MPL", which is the kind of false positive that gets a
    check disabled rather than fixed.
    """
    try:
        info = metadata(package)
    except Exception:  # pragma: no cover - dependency not installed
        pytest.skip(f"{package} not installed")

    classifiers = [c for c in (info.get_all("Classifier") or []) if c.startswith("License ::")]
    expression = info.get("License-Expression") or ""
    # The free-text License field is only a fallback, and only its first line: pandas puts
    # its entire LICENSE file there, bundled third-party notices included, so scanning the
    # whole thing finds licence names that belong to neither pandas nor us.
    free_text = (info.get("License") or "").strip().splitlines()
    fallback = free_text[0] if free_text and not classifiers and not expression else ""

    declared = " ".join([*classifiers, expression, fallback]).upper()
    assert declared.strip(), f"{package} declares no licence at all"

    for marker in COPYLEFT_MARKERS:
        assert not re.search(rf"\b{marker}\b", declared), (
            f"{package} declares {marker} in {declared!r}: it may not be on the import "
            "path (ADR-0003)"
        )


def test_pylint_is_reached_only_as_a_subprocess():
    """pylint is GPLv2+. It is supported, but only from the other side of a process
    boundary (ADR-0011)."""
    from dca.adapters.pylint_adapter import PylintAdapter

    assert PylintAdapter.path == "subprocess"
    source = (SRC / "adapters" / "pylint_adapter.py").read_text(encoding="utf-8")
    assert "import pylint" not in source
    assert "GPL" in source, "the licence constraint must be documented where it applies"


def test_every_subprocess_adapter_declares_its_path():
    """A copyleft engine mislabelled as an import would slip past the checks above."""
    from dca.adapters import ALL_ADAPTERS

    for cls in ALL_ADAPTERS:
        adapter = cls()
        if adapter.name in ("pylint",):
            assert adapter.path == "subprocess"
