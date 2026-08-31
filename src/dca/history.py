"""Metrics across a repository's git history — the time axis.

Every other capability in this package answers "what is this code like?". This one answers
"what has it been becoming?", which is a different and often more useful question: an
absolute complexity of 12 says little, while a complexity that went from 4 to 12 over six
months says a lot.

`wily` established the idea for Python and remains the reference for it. It is also stalled
(no release since October 2023) and wraps radon only, so it cannot see per-function tokens,
cognitive complexity, coupling or anything else added since. Rather than depend on a
stalled package, this module supplies the missing piece — iteration over revisions — and
lets the existing engines do the measuring. That is orchestration, not reimplementation, so
it does not breach ADR-0001: no metric is computed here.

Design notes worth knowing before you trust the output:

* **Files are read from git, never from the working tree.** ``git show <rev>:<path>`` gives
  the content as it was, so an uncommitted edit cannot contaminate a historical point.
* **A file that did not exist at a revision is absent, not zero.** Rows only appear for
  paths that existed, which keeps a project's growth from reading as a metric collapsing.
* **Revisions are sampled, not exhausted, by default.** Measuring 8 engines across 10,000
  commits is hours of work to answer a question that 40 evenly spaced points answer as
  well. ``every`` controls the stride.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .core import Analyser
from .execution import run, which


class GitUnavailableError(RuntimeError):
    """git is not installed, or the path is not a repository."""


@dataclass(frozen=True, slots=True)
class Revision:
    """One point in history."""

    sha: str
    timestamp: str
    author: str
    subject: str


def _git(repo: str, *args: str, timeout: int = 60) -> str:
    binary = which("git")
    if binary is None:
        raise GitUnavailableError("git is not installed")
    result = run([binary, "-C", repo, *args], timeout=timeout)
    if not result.ok:
        raise GitUnavailableError(
            f"git {' '.join(args[:2])} failed in {repo}: {result.stderr[:200]!r}"
        )
    return result.stdout


def revisions(repo: str, *, branch: str = "HEAD", limit: int = 200) -> list[Revision]:
    """The revision log, newest first.

    The unit separator is used as the field delimiter rather than a comma or a pipe:
    commit subjects contain every printable character a person can type, and a delimiter
    that can appear in the data is a parser waiting to be wrong.
    """
    raw = _git(
        repo, "log", branch, f"--max-count={limit}", "--format=%H\x1f%aI\x1f%an\x1f%s"
    )
    out = []
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4:
            out.append(Revision(*parts))
    return out


def files_at(repo: str, sha: str, *, suffix: str = ".py") -> list[str]:
    """Paths ending in ``suffix`` as they existed at ``sha``.

    Filtering happens here rather than in git. ``ls-tree -- '*.py'`` looks like it should
    work and silently matches nothing, because git anchors pathspecs at the tree root
    unless given glob magic. Listing everything and filtering in Python is one line longer
    and cannot be defeated by quoting rules.
    """
    raw = _git(repo, "ls-tree", "-r", "--name-only", sha)
    return [line for line in raw.splitlines() if line.strip().endswith(suffix)]


def content_at(repo: str, sha: str, path: str) -> str | None:
    """A file's content at a revision, or None if it did not exist then."""
    try:
        return _git(repo, "show", f"{sha}:{path}")
    except GitUnavailableError:
        return None


def measure(
    repo: str,
    *,
    branch: str = "HEAD",
    limit: int = 200,
    every: int = 1,
    paths: list[str] | None = None,
    engines: list[str] | None = None,
    max_files_per_revision: int = 50,
) -> pd.DataFrame:
    """Measure the repository at a series of revisions.

    Returns one row per (revision, file), carrying the revision's identity alongside every
    metric column, so the result groups naturally by either axis.

    ``engines`` defaults to the import-path engines. That is deliberate: a subprocess
    engine costs a process per file per revision, which turns a minute into an afternoon.
    Pass them explicitly when the question is worth the wait.
    """
    log = revisions(repo, branch=branch, limit=limit)
    if not log:
        return pd.DataFrame()
    sampled = log[::every] if every > 1 else log
    # The log arrives newest-first; index from the oldest so the number increases with
    # time. Ordering by it rather than by timestamp is deliberate: commit timestamps tie
    # (several commits in one second) and can even run backwards after a rebase or an
    # amended date, so a chart sorted by timestamp is not reliably a chart of history.
    order = {rev.sha: i for i, rev in enumerate(reversed(sampled))}

    analyser = Analyser(engines=engines or ["radon", "lizard", "ast", "complexipy"])
    rows: list[dict] = []

    for revision in sampled:
        try:
            tracked = paths or files_at(repo, revision.sha)
        except GitUnavailableError:
            continue
        # A bound per revision keeps one enormous commit from dominating the run. Sorted
        # first so the same files are chosen at every revision and the series stays
        # comparable rather than drifting with directory order.
        for path in sorted(tracked)[:max_files_per_revision]:
            source = content_at(repo, revision.sha, path)
            if source is None:
                continue  # absent at this revision: no row, not a zero
            result = analyser.analyse(source, fragment_id=f"{revision.sha[:12]}:{path}")
            rows.append(
                {
                    "sha": revision.sha,
                    "revision_index": order[revision.sha],
                    "timestamp": revision.timestamp,
                    "author": revision.author,
                    "subject": revision.subject,
                    "path": path,
                    "is_valid_python": result.is_valid_python,
                    **result.metrics,
                }
            )

    return pd.DataFrame(rows)


def trend(frame: pd.DataFrame, column: str, *, how: str = "sum") -> pd.DataFrame:
    """Collapse a history frame to one value per revision, oldest first.

    ``sum`` answers "how much of this does the project contain"; ``mean`` answers "what is
    the typical file like". They tell different stories about the same repository — a
    project can grow steadily while its average file stays exactly as complex — so the
    choice is the caller's rather than a default worth hiding.
    """
    if frame.empty or column not in frame.columns:
        return pd.DataFrame()
    grouped = frame.groupby(
        ["revision_index", "sha", "timestamp"], as_index=False
    )[column].agg(how)
    return grouped.sort_values("revision_index", ignore_index=True)
