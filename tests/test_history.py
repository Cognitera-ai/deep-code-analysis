"""Metrics across git history — the capability wily established and then stopped shipping."""

from __future__ import annotations

import subprocess

import pytest

from dca.execution import which
from dca.history import GitUnavailableError, content_at, files_at, measure, revisions, trend


@pytest.fixture(scope="module")
def repo(tmp_path_factory) -> str:
    """A small repository with three revisions and a file that grows."""
    if which("git") is None:
        pytest.skip("git not installed")
    path = tmp_path_factory.mktemp("historyrepo")

    def git(*args):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "Test")

    (path / "grows.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "first")

    (path / "grows.py").write_text("x = 1\ny = 2\nz = 3\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "second")

    (path / "grows.py").write_text(
        "x = 1\ny = 2\nz = 3\n\n\ndef f(a):\n    return a + 1\n", encoding="utf-8"
    )
    (path / "added_later.py").write_text("w = 9\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "third")
    return str(path)


def test_revisions_are_newest_first(repo):
    log = revisions(repo)
    assert [r.subject for r in log] == ["third", "second", "first"]
    assert all(len(r.sha) == 40 for r in log)


def test_content_is_read_from_git_not_the_working_tree(repo, tmp_path):
    """A dirty working tree must not contaminate a historical measurement."""
    log = revisions(repo)
    oldest = log[-1].sha

    from pathlib import Path

    Path(repo, "grows.py").write_text("# uncommitted junk\n" * 50, encoding="utf-8")
    try:
        assert content_at(repo, oldest, "grows.py") == "x = 1\n"
    finally:
        Path(repo, "grows.py").write_text(
            "x = 1\ny = 2\nz = 3\n\n\ndef f(a):\n    return a + 1\n", encoding="utf-8"
        )


def test_a_file_absent_at_a_revision_produces_no_row(repo):
    """Not a zero. A project growing must not read as a metric collapsing."""
    frame = measure(repo, engines=["radon"])
    by_path = frame.groupby("path")["sha"].count()

    assert by_path["grows.py"] == 3
    assert by_path["added_later.py"] == 1


def test_growth_is_visible_in_the_trend(repo):
    frame = measure(repo, engines=["radon"], paths=["grows.py"])
    series = trend(frame, "lloc__radon")

    values = list(series["lloc__radon"])
    assert values == sorted(values), "oldest-first ordering, and the file only grew"
    assert values[0] < values[-1]


def test_stride_samples_the_history(repo):
    every_one = measure(repo, engines=["radon"], paths=["grows.py"])
    every_two = measure(repo, engines=["radon"], paths=["grows.py"], every=2)

    assert len(every_two) < len(every_one)


def test_a_non_repository_fails_clearly(tmp_path):
    with pytest.raises(GitUnavailableError):
        revisions(str(tmp_path))


def test_files_at_lists_only_python(repo):
    log = revisions(repo)
    assert all(f.endswith(".py") for f in files_at(repo, log[0].sha))
