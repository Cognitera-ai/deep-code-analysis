"""End-to-end parity: our adapters against each engine's own command line interface.

This is the test that answers "did we break anything by wrapping it?".

The comparison is deliberately made across **two independent code paths**. Our adapters
call each engine's Python API; this test drives each engine's **CLI**, the way a user
would from a shell, and parses its machine-readable output. If the two agree over a large
body of real code, the adapter is passing values through rather than transforming them. If
they disagree, the adapter is distorting the thing it promised only to delegate.

The corpus is real Python: every parseable ``.py`` file in the environment's
``site-packages``. Thousands of files, written by hundreds of people for reasons that have
nothing to do with this package. That is much better evidence than fixtures written by the
same person who wrote the adapters, because nobody chose these files to make the test pass.

What this test can and cannot establish (ADR-0010):

* It **can** show the adapters reproduce their engines. That is a claim about this package.
* It **cannot** show any metric is "correct". There is no oracle: radon and lizard disagree
  with each other by an order of magnitude, so agreeing with both is impossible and
  agreeing with one is not correctness.

Set ``DCA_PARITY_SAMPLE`` to widen the sample for a deeper run::

    DCA_PARITY_SAMPLE=400 pytest tests/conformance/test_engine_parity.py -v
"""

from __future__ import annotations

import ast
import csv
import glob
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from dca.adapters.ast_adapter import AstAdapter
from dca.adapters.complexipy_adapter import ComplexipyAdapter
from dca.adapters.lizard_adapter import LizardAdapter
from dca.adapters.radon_adapter import RadonAdapter
from dca.execution import which

#: Files sampled for the fast (CI) run. Enough real code to catch a systematic error;
#: small enough that the batch CLI invocations stay quick.
SAMPLE_SIZE = int(os.getenv("DCA_PARITY_SAMPLE", "120"))
#: Subprocess engines are compared on a smaller subset: they cost a process per file on
#: both sides of the comparison.
SUBPROCESS_SAMPLE = int(os.getenv("DCA_PARITY_SUBPROCESS_SAMPLE", "12"))

BIN = Path(sys.executable).parent


def _corpus_files() -> list[str]:
    """Real Python files from the environment, deterministically sampled."""
    roots = [
        str(Path(sys.prefix) / "lib" / f"python3.{sys.version_info.minor}" / "site-packages"),
        str(Path(sys.prefix) / "lib" / "site-packages"),
    ]
    candidates: list[str] = []
    for root in roots:
        candidates.extend(glob.glob(f"{root}/**/*.py", recursive=True))

    usable = []
    for path in candidates:
        try:
            source = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        # Skip the trivial and the enormous: neither tells us anything the middle does not,
        # and the enormous makes the CLI comparison slow for no extra signal.
        if not (20 < len(source) < 200_000):
            continue
        try:
            ast.parse(source)
        except (SyntaxError, ValueError):
            continue
        usable.append(path)

    random.seed(0)  # deterministic: a flaky corpus makes a flaky test
    return sorted(random.sample(usable, min(SAMPLE_SIZE, len(usable))))


@pytest.fixture(scope="module")
def corpus_paths() -> list[str]:
    files = _corpus_files()
    if len(files) < 20:
        pytest.skip("no substantial Python corpus found in this environment")
    return files


@pytest.fixture(scope="module")
def sources(corpus_paths) -> dict[str, str]:
    return {p: Path(p).read_text(encoding="utf-8") for p in corpus_paths}


def _run_cli(argv: list[str]) -> str:
    result = subprocess.run(argv, capture_output=True, text=True, timeout=600)
    return result.stdout


def _report(mismatches: list[str], checked: int, what: str) -> None:
    """Fail with every mismatch, not just the first.

    One mismatch tells you something broke; the full list tells you whether it is one
    pathological file or a systematic error, and that distinction is the whole diagnosis.
    """
    if mismatches:
        shown = "\n".join(f"  {m}" for m in mismatches[:25])
        more = f"\n  ... and {len(mismatches) - 25} more" if len(mismatches) > 25 else ""
        pytest.fail(
            f"{len(mismatches)} of {checked} {what} disagreed with the engine's own CLI:\n"
            f"{shown}{more}"
        )
    assert checked > 0, f"no {what} were actually compared"


# ── radon ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def radon_cli(corpus_paths) -> dict[str, dict]:
    """radon's own CLI output for the whole corpus, in one invocation per subcommand."""
    binary = which("radon")
    if binary is None:
        pytest.skip("radon CLI not on PATH")
    out = {}
    for sub, args in [("raw", []), ("hal", []), ("mi", []), ("cc", ["-s"])]:
        raw = _run_cli([binary, sub, "-j", *args, *corpus_paths])
        out[sub] = json.loads(raw) if raw.strip() else {}
    return out


def test_radon_size_metrics_match_the_cli(sources, radon_cli):
    """Every raw counter, passed through untouched."""
    adapter = RadonAdapter()
    mismatches, checked = [], 0
    mapping = {
        "lloc": "lloc", "sloc": "sloc", "comments": "comments",
        "single_comments": "single_comments", "multi_line_comments": "multi",
        "blank_lines": "blank", "total_lines": "loc",
    }
    for path, source in sources.items():
        expected = radon_cli["raw"].get(path)
        if not isinstance(expected, dict) or "loc" not in expected:
            continue
        ours = adapter.analyse(source).values
        checked += 1
        for our_key, cli_key in mapping.items():
            if ours[our_key] != expected[cli_key]:
                mismatches.append(f"{path}: {our_key} ours={ours[our_key]} cli={expected[cli_key]}")
    _report(mismatches, checked, "files")


def test_radon_halstead_matches_the_cli(sources, radon_cli):
    """Including the zeros, which are the values this package exists to talk about."""
    adapter = RadonAdapter()
    mismatches, checked = [], 0
    mapping = {
        "halstead_h1": "h1", "halstead_h2": "h2", "halstead_n1": "N1", "halstead_n2": "N2",
        "halstead_vocabulary": "vocabulary", "halstead_length": "length",
        "halstead_volume": "volume", "halstead_difficulty": "difficulty",
        "halstead_effort": "effort", "halstead_time": "time", "halstead_bugs": "bugs",
    }
    for path, source in sources.items():
        entry = radon_cli["hal"].get(path)
        if not isinstance(entry, dict) or "total" not in entry:
            continue
        expected = entry["total"]
        ours = adapter.analyse(source).values
        checked += 1
        for our_key, cli_key in mapping.items():
            if ours[our_key] != pytest.approx(expected[cli_key], abs=1e-6):
                mismatches.append(f"{path}: {our_key} ours={ours[our_key]} cli={expected[cli_key]}")
    _report(mismatches, checked, "files")


def test_radon_maintainability_matches_the_cli(sources, radon_cli):
    adapter = RadonAdapter()
    mismatches, checked = [], 0
    for path, source in sources.items():
        entry = radon_cli["mi"].get(path)
        if not isinstance(entry, dict) or "mi" not in entry:
            continue
        ours = adapter.analyse(source).values["maintainability_index"]
        checked += 1
        if ours != pytest.approx(entry["mi"], abs=1e-6):
            mismatches.append(f"{path}: mi ours={ours} cli={entry['mi']}")
    _report(mismatches, checked, "files")


def test_radon_cyclomatic_complexity_matches_the_cli(sources, radon_cli):
    """The aggregation is ours; the per-block numbers must be radon's exactly."""
    adapter = RadonAdapter()
    mismatches, checked = [], 0
    for path, source in sources.items():
        entries = radon_cli["cc"].get(path)
        if not isinstance(entries, list):
            continue
        complexities = [
            e["complexity"] for e in entries if isinstance(e, dict) and "complexity" in e
        ]
        if not complexities:
            continue  # the imputation path, covered by its own test
        ours = adapter.analyse(source).values
        checked += 1
        expected_mean = round(sum(complexities) / len(complexities), 4)
        if ours["cyclomatic_complexity_max"] != max(complexities):
            mismatches.append(
                f"{path}: cc_max ours={ours['cyclomatic_complexity_max']} cli={max(complexities)}"
            )
        if ours["cyclomatic_complexity_mean"] != pytest.approx(expected_mean, abs=1e-4):
            mismatches.append(
                f"{path}: cc_mean ours={ours['cyclomatic_complexity_mean']} cli={expected_mean}"
            )
        if ours["cc_imputed_module_level"] is not False:
            mismatches.append(f"{path}: flagged as imputed although radon reported blocks")
    _report(mismatches, checked, "files")


# ── lizard ───────────────────────────────────────────────────────────────────────────


def test_lizard_matches_the_cli(sources, corpus_paths):
    """Per-function metrics, compared against lizard's own CSV.

    The CSV columns are, in order: **NLOC, CCN**, token_count, parameter_count, length,
    location, file, function, signature, start, end. That first pair is easy to get
    backwards — this test did, initially — and the mistake is invisible because both are
    small integers. It is caught here only because swapping them makes the two columns
    disagree with each other in opposite directions on the same file.

    The adapter itself is immune to this: it reads named attributes from lizard's Python
    API (``f.cyclomatic_complexity``, ``f.nloc``) rather than positional CSV fields.
    """
    binary = which("lizard")
    if binary is None:
        pytest.skip("lizard CLI not on PATH")

    raw = _run_cli([binary, "--csv", *corpus_paths])
    by_file: dict[str, list[dict]] = {}
    for row in csv.reader(raw.splitlines()):
        if len(row) < 11:
            continue
        by_file.setdefault(row[6], []).append(
            {"nloc": int(row[0]), "ccn": int(row[1]), "tokens": int(row[2]), "params": int(row[3])}
        )

    adapter = LizardAdapter()
    mismatches, checked = [], 0
    for path, source in sources.items():
        expected = by_file.get(path, [])
        ours = adapter.analyse(source).values
        if ours.get("function_count") is None:
            continue
        checked += 1
        if ours["function_count"] != len(expected):
            mismatches.append(
                f"{path}: function_count ours={ours['function_count']} cli={len(expected)}"
            )
            continue
        if not expected:
            continue
        checks = {
            "cyclomatic_complexity_max": max(r["ccn"] for r in expected),
            "avg_token_count_max": max(r["tokens"] for r in expected),
            "avg_param_count_max": max(r["params"] for r in expected),
            "function_length_max": max(r["nloc"] for r in expected),
        }
        for key, want in checks.items():
            if ours[key] != want:
                mismatches.append(f"{path}: {key} ours={ours[key]} cli={want}")
        want_mean = round(sum(r["ccn"] for r in expected) / len(expected), 4)
        if ours["cyclomatic_complexity_mean"] != pytest.approx(want_mean, abs=1e-4):
            mismatches.append(
                f"{path}: cc_mean ours={ours['cyclomatic_complexity_mean']} cli={want_mean}"
            )
    _report(mismatches, checked, "files")


# ── complexipy ───────────────────────────────────────────────────────────────────────


def test_complexipy_matches_the_cli(sources, corpus_paths, tmp_path_factory):
    """Cognitive complexity, compared against complexipy's own JSON export."""
    binary = which("complexipy")
    if binary is None:
        pytest.skip("complexipy CLI not on PATH")

    out_file = tmp_path_factory.mktemp("complexipy") / "out.json"
    subprocess.run(
        [binary, "--output-format", "json", "--output", str(out_file), "-q", *corpus_paths],
        capture_output=True,
        text=True,
        timeout=600,
    )
    if not out_file.exists():
        pytest.skip("complexipy produced no JSON export in this version")

    # complexipy echoes the path exactly as it was given on the command line, so both
    # sides are resolved before matching.
    by_file: dict[str, list[int]] = {}
    for entry in json.loads(out_file.read_text(encoding="utf-8")):
        key = str(Path(entry["path"]).resolve())
        by_file.setdefault(key, []).append(entry["complexity"])

    adapter = ComplexipyAdapter()
    mismatches, checked = [], 0
    for path, source in sources.items():
        expected = by_file.get(str(Path(path).resolve()))
        if expected is None:
            continue
        ours = adapter.analyse(source).values
        if ours.get("cognitive_complexity_max") is None:
            continue
        checked += 1
        if ours["cognitive_complexity_max"] != max(expected):
            mismatches.append(
                f"{path}: cognitive max ours={ours['cognitive_complexity_max']} cli={max(expected)}"
            )
        want_mean = round(sum(expected) / len(expected), 4)
        if ours["cognitive_complexity_mean"] != pytest.approx(want_mean, abs=1e-4):
            mismatches.append(
                f"{path}: cognitive mean ours={ours['cognitive_complexity_mean']} cli={want_mean}"
            )
    _report(mismatches, checked, "files")


# ── ast (the one adapter that computes rather than delegates) ────────────────────────


def test_ast_metrics_recompute_exactly(sources):
    """No CLI exists for these, so they are checked against a direct recomputation.

    This adapter is the sanctioned exception to "delegate, never reimplement", precisely
    because no public tool emits AST depth or node counts as named metrics. Having no
    upstream to defer to, its definitions have to be simple enough to verify by restating
    them — which is what this does.
    """
    adapter = AstAdapter()
    mismatches, checked = [], 0
    for path, source in sources.items():
        ours = adapter.analyse(source).values
        if ours.get("total_nodes") is None:
            continue
        nodes = list(ast.walk(ast.parse(source)))
        checked += 1
        expected = {
            "total_nodes": len(nodes),
            "call_count": sum(isinstance(n, ast.Call) for n in nodes),
            "return_count": sum(isinstance(n, ast.Return) for n in nodes),
            "classdef_count": sum(isinstance(n, ast.ClassDef) for n in nodes),
            "try_count": sum(isinstance(n, ast.Try) for n in nodes),
            "functiondef_count": sum(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in nodes
            ),
        }
        for key, want in expected.items():
            if ours[key] != want:
                mismatches.append(f"{path}: {key} ours={ours[key]} expected={want}")
        # Ratios must be consistent with their own denominator.
        loops = sum(isinstance(n, (ast.For, ast.While, ast.AsyncFor)) for n in nodes)
        if ours["loop_ratio"] != pytest.approx(round(loops / len(nodes), 6), abs=1e-6):
            mismatches.append(f"{path}: loop_ratio inconsistent with total_nodes")
    _report(mismatches, checked, "files")


# ── subprocess engines ───────────────────────────────────────────────────────────────


def test_bandit_matches_the_cli(sources):
    """Our adapter shells out too, but into a temp directory with a renamed file. This
    checks that the rename and the temp directory do not change what bandit reports."""
    binary = which("bandit")
    if binary is None:
        pytest.skip("bandit not installed")

    from dca.adapters.bandit_adapter import BanditAdapter

    adapter = BanditAdapter()
    subset = list(sources.items())[:SUBPROCESS_SAMPLE]
    mismatches, checked = [], 0
    for path, source in subset:
        raw = _run_cli([binary, "-f", "json", "-q", path])
        if not raw.strip():
            continue
        totals = (json.loads(raw).get("metrics") or {}).get("_totals") or {}
        ours = adapter.analyse(source).values
        if ours.get("security_issues") is None:
            continue
        checked += 1
        for our_key, cli_key in [
            ("security_severity_high", "SEVERITY.HIGH"),
            ("security_severity_medium", "SEVERITY.MEDIUM"),
            ("security_severity_low", "SEVERITY.LOW"),
            ("security_confidence_high", "CONFIDENCE.HIGH"),
        ]:
            want = int(totals.get(cli_key, 0))
            if ours[our_key] != want:
                mismatches.append(f"{path}: {our_key} ours={ours[our_key]} cli={want}")
    _report(mismatches, checked, "files")


def test_vulture_matches_the_cli(sources, tmp_path_factory):
    """Compared like for like: the CLI is run on a file with the same name our adapter uses.

    That qualifier is load-bearing, and the next test explains why.
    """
    binary = which("vulture")
    if binary is None:
        pytest.skip("vulture not installed")

    from dca.adapters.vulture_adapter import VultureAdapter

    adapter = VultureAdapter()
    workspace = tmp_path_factory.mktemp("vulture-parity")
    subset = list(sources.items())[:SUBPROCESS_SAMPLE]
    mismatches, checked = [], 0
    for path, source in subset:
        staged = workspace / "fragment.py"
        staged.write_text(source, encoding="utf-8")
        raw = _run_cli([binary, str(staged)])
        want = sum(1 for line in raw.splitlines() if "unused" in line and "confidence" in line)
        ours = adapter.analyse(source).values
        if ours.get("dead_code_items") is None:
            continue
        checked += 1
        if ours["dead_code_items"] != want:
            mismatches.append(f"{path}: dead_code_items ours={ours['dead_code_items']} cli={want}")
    _report(mismatches, checked, "files")


def test_vulture_output_depends_on_the_path(tmp_path_factory):
    """A documented limitation, pinned so it cannot regress into a silent surprise.

    vulture applies pytest conventions to decide what is reachable: ``Test*`` classes and
    ``test_*`` methods are assumed to be called by a test runner. What is easy to miss is
    that the trigger is **any component of the path**, not just the filename — a file
    called ``fragment.py`` inside a directory called ``test_stuff/`` is whitelisted exactly
    as ``test_stuff.py`` would be.

    That has a direct consequence for this package. It analyses **fragments**, which are
    strings with no path, so the adapter necessarily invents one. It writes to
    ``fragment.py`` inside a temporary directory prefixed ``dca-vulture-``: both components
    are deliberately neutral, so the numbers reported are the numbers for ordinary code.
    Change either to something containing "test" and every count would silently drop.

    Found by the parity test on a real numpy test file — 4 findings under its own name, 8
    under ours — and then narrowed to the directory. Note that this test cannot use
    pytest's ``tmp_path``: that fixture puts everything under a directory named after the
    *test function*, which vulture whitelists, so the "neutral" control would not be
    neutral. Even writing the test is a demonstration of how quietly this triggers.
    """
    root = tmp_path_factory.mktemp("vulturepaths")
    binary = which("vulture")
    if binary is None:
        pytest.skip("vulture not installed")

    source = (
        "import pytest\n\n\n"
        "class TestThing:\n"
        "    def test_one(self):\n"
        "        assert True\n"
    )

    def findings(directory: str, filename: str) -> int:
        target = root / directory
        target.mkdir(exist_ok=True)
        path = target / filename
        path.write_text(source, encoding="utf-8")
        raw = _run_cli([binary, str(path)])
        return sum(1 for line in raw.splitlines() if "unused" in line and "confidence" in line)

    neutral = findings("neutral", "fragment.py")
    by_filename = findings("neutral", "test_thing.py")
    by_directory = findings("test_suite", "fragment.py")

    assert by_filename < neutral, "vulture no longer whitelists by filename"
    assert by_directory < neutral, "vulture no longer whitelists by directory name"


def test_the_vulture_adapter_uses_a_neutral_temporary_path():
    """Guards the invariant the previous test explains.

    If either the directory prefix or the filename picked up a "test" component, every
    dead-code count would drop without any test failing — the numbers would still be
    internally consistent, just measuring a different thing.
    """
    from dca.adapters import vulture_adapter

    source = Path(vulture_adapter.__file__).read_text(encoding="utf-8")
    assert 'prefix="dca-vulture-"' in source
    assert '"fragment.py"' in source
    for component in ("dca-vulture-", "fragment.py"):
        assert "test" not in component.lower()


# ── aggregation coverage ─────────────────────────────────────────────────────────────


def test_every_radon_cli_field_is_carried_or_deliberately_dropped(radon_cli):
    """The other half of the promise: we did not just avoid breaking the engines, we
    actually carry what they produce.

    Any field radon's CLI emits must either be in our schema or be named here with a
    reason. A field that is silently absent is a metric we claimed to aggregate and did
    not.
    """
    from dca.adapters.radon_adapter import RadonAdapter

    declared = {spec.key for spec in RadonAdapter().declared_metrics}

    # Presentation and derived values, deliberately excluded.
    excluded = {
        "rank": "a letter grade derived from the number; the number is carried",
        "calculated_length": "Halstead's predicted length, a function of h1 and h2, both carried",
        "closures": "structure, not a metric",
        "type": "structure, not a metric",
        "name": "structure, not a metric",
        "lineno": "position, not a metric",
        "endline": "position, not a metric",
        "col_offset": "position, not a metric",
        "classname": "structure, not a metric",
        "methods": "structure, not a metric",
        "complexity": "carried as cyclomatic_complexity_mean/max/module",
    }

    cli_to_ours = {
        "loc": "total_lines", "lloc": "lloc", "sloc": "sloc", "comments": "comments",
        "multi": "multi_line_comments", "blank": "blank_lines",
        "single_comments": "single_comments", "mi": "maintainability_index",
        "h1": "halstead_h1", "h2": "halstead_h2", "N1": "halstead_n1", "N2": "halstead_n2",
        "vocabulary": "halstead_vocabulary", "length": "halstead_length",
        "volume": "halstead_volume", "difficulty": "halstead_difficulty",
        "effort": "halstead_effort", "time": "halstead_time", "bugs": "halstead_bugs",
    }

    seen: set[str] = set()
    for entry in radon_cli["raw"].values():
        if isinstance(entry, dict):
            seen |= set(entry)
    for entry in radon_cli["mi"].values():
        if isinstance(entry, dict):
            seen |= set(entry)
    for entry in radon_cli["hal"].values():
        if isinstance(entry, dict) and isinstance(entry.get("total"), dict):
            seen |= set(entry["total"])
    for entries in radon_cli["cc"].values():
        if isinstance(entries, list):
            for e in entries:
                if isinstance(e, dict):
                    seen |= set(e)

    unaccounted = []
    for field in sorted(seen):
        if field in excluded:
            continue
        ours = cli_to_ours.get(field)
        if ours is None or ours not in declared:
            unaccounted.append(field)

    assert not unaccounted, (
        f"radon's CLI emits fields we neither carry nor explain: {unaccounted}. "
        "Either add them to the schema or list them in `excluded` with a reason."
    )


def test_lexical_metrics_match_a_reference_implementation(sources):
    """Parity against an independent implementation of the same definitions.

    The lexical adapter has no upstream CLI to check against — no public tool emits these
    — so it is checked against a second implementation written separately for a research
    platform. Agreement over hundreds of real files is what makes it credible that the
    definitions are the ones intended rather than the ones that happened to be coded.

    The definitions being pinned: layout tokens and comments are excluded, docstrings are
    not, dotted calls count by their last segment, and a name may count in more than one
    kind.
    """
    from dca.adapters.lexical_adapter import LexicalAdapter

    adapter = LexicalAdapter()
    mismatches, checked = [], 0

    for path, source in sources.items():
        values = adapter.analyse(source).values
        if values.get("distinct_tokens") is None:
            continue
        checked += 1

        # Recompute independently, from the definitions rather than from the adapter.
        import ast
        import io
        import keyword
        import tokenize

        try:
            tokens = [
                t
                for t in tokenize.generate_tokens(io.StringIO(source).readline)
                if t.type
                not in {
                    tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.ENDMARKER, tokenize.COMMENT,
                }
            ]
        except (tokenize.TokenError, IndentationError):
            continue

        words = [t.string for t in tokens]
        identifiers = {
            t.string for t in tokens
            if t.type == tokenize.NAME and not keyword.iskeyword(t.string)
        }
        functions = {
            n.name for n in ast.walk(ast.parse(source))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        for key, want in (
            ("distinct_tokens", len(set(words))),
            ("lexical_tokens", len(words)),
            ("distinct_identifiers", len(identifiers)),
            ("distinct_functions_defined", len(functions)),
        ):
            if values[key] != want:
                mismatches.append(f"{path}: {key} ours={values[key]} expected={want}")

    _report(mismatches, checked, "files")
