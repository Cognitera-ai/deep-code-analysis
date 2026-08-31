"""Command line interface.

Three commands, and the third matters more than it looks. With seven engines, "why is this
column empty?" is the most common question a user will have, and ``dca doctor`` is the
one-command answer: it reports which engines are present, at what version, and how they are
reached. Without it, a missing subprocess binary is indistinguishable from a corpus where
the metric does not apply.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .adapters import build as build_adapters
from .catalogue import generate as generate_catalogue
from .core import Analyser


def _read_sources(paths: list[str]) -> dict[str, str]:
    """Read fragments from files, directories, or stdin when given ``-``."""
    fragments: dict[str, str] = {}
    for raw in paths:
        if raw == "-":
            fragments["<stdin>"] = sys.stdin.read()
            continue
        path = Path(raw)
        if path.is_dir():
            for file in sorted(path.rglob("*.py")):
                fragments[str(file)] = file.read_text(encoding="utf-8", errors="replace")
        elif path.is_file():
            fragments[str(path)] = path.read_text(encoding="utf-8", errors="replace")
        else:
            raise SystemExit(f"no such file or directory: {raw}")
    if not fragments:
        raise SystemExit("no Python fragments found in the given paths")
    return fragments


def _cmd_analyse(args: argparse.Namespace) -> int:
    fragments = _read_sources(args.paths)
    analyser = Analyser(engines=args.engines, include_optional=args.include_optional)
    frame = analyser.analyse_many(fragments)

    if args.out:
        writer = frame.to_parquet if args.format == "parquet" else frame.to_csv
        written = writer(args.out)
        for name, path in written.items():
            print(f"{name:14s} {path}")
    else:
        from . import console as ui

        metrics = frame.metrics()
        divergent_cols = [c for c in metrics.columns if c.endswith("__divergent")]
        rows = [
            {
                "fragment": str(row["fragment_id"]),
                "valid": bool(row.get("is_valid_python")),
                "lloc": row.get("lloc__radon"),
                "cc": row.get("cyclomatic_complexity_mean__radon"),
                "divergent": sum(1 for c in divergent_cols if row.get(c) is True),
            }
            for _, row in metrics.iterrows()
        ]
        ui.print_overview(rows, len(metrics.columns) - 4)

    degradations = frame.degradations()
    if not degradations.empty:
        print(f"\n{len(degradations)} degradation(s) recorded:", file=sys.stderr)
        for _, row in degradations.iterrows():
            print(f"  {row['engine']}: {row['detail']}", file=sys.stderr)

    if args.summary:
        from . import console as ui

        summary = frame.divergence_summary()
        if not summary.empty:
            ui.print_divergence(summary.to_dict("records"))
    return 0


def with_pandas_width(frame) -> None:
    """Print a frame without pandas truncating it into uselessness."""
    import pandas as pd

    with pd.option_context("display.max_columns", None, "display.width", 200):
        print(frame.to_string(index=False))


def _cmd_catalogue(args: argparse.Namespace) -> int:
    adapters = build_adapters(args.engines, include_optional=True)
    text = generate_catalogue(adapters)
    if args.write:
        path = Path(args.write)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print(f"wrote {path}")
    else:
        print(text, end="")
    return 0


def _cmd_history(args: argparse.Namespace) -> int:
    """Measure a repository across its git history."""
    from .history import GitUnavailableError, measure, trend

    try:
        frame = measure(
            args.repo,
            branch=args.branch,
            limit=args.limit,
            every=args.every,
            engines=args.engines,
            max_files_per_revision=args.max_files,
        )
    except GitUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if frame.empty:
        print("no measurable Python found in that history", file=sys.stderr)
        return 1

    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        path = out / ("dca_history.parquet" if args.format == "parquet" else "dca_history.csv")
        if args.format == "parquet":
            frame.to_parquet(path, index=False)
        else:
            frame.to_csv(path, index=False)
        print(f"{len(frame)} rows -> {path}")
    elif args.trend:
        series = trend(frame, args.trend, how=args.how)
        if series.empty:
            print(f"error: no column named {args.trend!r}", file=sys.stderr)
            return 2
        with_pandas_width(series)
    else:
        with_pandas_width(frame.head(50))
    return 0


def _cmd_explore(args: argparse.Namespace) -> int:
    """Open the interactive divergence explorer."""
    from .tui import TuiUnavailableError, explore_paths

    try:
        explore_paths(args.paths, engines=args.engines)
    except TuiUnavailableError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Report engine availability. Exits non-zero if a default engine is missing."""
    from . import console as ui

    adapters = build_adapters(None, include_optional=True)
    missing_default = False
    default_names = {a.name for a in build_adapters(None)}

    rows = []
    for adapter in adapters:
        available = adapter.is_available()
        optional = adapter.name not in default_names
        if available:
            status = "available"
        elif optional:
            status = "optional, off"
        else:
            status = "MISSING"
            missing_default = True
        rows.append(
            {
                "name": adapter.name,
                "path": adapter.path,
                "status": status,
                "version": adapter.version or "-",
            }
        )

    from . import embeddings

    ui.print_doctor(rows, __version__, embeddings.is_available())

    if missing_default:
        print(
            "\nA default engine is missing. Its columns will be null for every fragment.\n"
            "Subprocess engines install with: pip install pyscn vulture bandit",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dca",
        description=(
            "Structural measurement of Python code, with provenance and engine divergence "
            "made explicit."
        ),
    )
    parser.add_argument("--version", action="version", version=f"dca {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyse = subparsers.add_parser("analyse", help="measure files, a directory, or stdin")
    analyse.add_argument("paths", nargs="+", help="files, directories, or - for stdin")
    analyse.add_argument("--format", choices=["csv", "parquet"], default="csv")
    analyse.add_argument(
        "--out", help="directory to write tables into; prints to stdout if omitted"
    )
    analyse.add_argument("--engines", nargs="+", help="restrict to these engines")
    analyse.add_argument(
        "--include-optional", action="store_true", help="also run optional engines (pylint)"
    )
    analyse.add_argument("--summary", action="store_true", help="print the divergence summary")
    analyse.set_defaults(func=_cmd_analyse)

    catalogue = subparsers.add_parser("catalogue", help="print the generated metric catalogue")
    catalogue.add_argument("--engines", nargs="+", help="restrict to these engines")
    catalogue.add_argument("--write", help="write to this path instead of stdout")
    catalogue.set_defaults(func=_cmd_catalogue)

    history = subparsers.add_parser(
        "history", help="measure a repository across its git history"
    )
    history.add_argument("repo", help="path to a git repository")
    history.add_argument("--branch", default="HEAD")
    history.add_argument("--limit", type=int, default=100, help="revisions to consider")
    history.add_argument(
        "--every", type=int, default=1, help="sample every Nth revision (stride)"
    )
    history.add_argument("--max-files", type=int, default=50, help="files per revision")
    history.add_argument("--engines", nargs="+", help="restrict to these engines")
    history.add_argument("--trend", help="collapse to one value per revision for this column")
    history.add_argument("--how", default="sum", choices=["sum", "mean", "max", "min"])
    history.add_argument("--format", choices=["csv", "parquet"], default="csv")
    history.add_argument("--out", help="directory to write into")
    history.set_defaults(func=_cmd_history)

    explore = subparsers.add_parser(
        "explore", help="interactively browse where the engines disagree (needs the tui extra)"
    )
    explore.add_argument("paths", nargs="+", help="files or directories to analyse")
    explore.add_argument("--engines", nargs="+", help="restrict to these engines")
    explore.set_defaults(func=_cmd_explore)

    doctor = subparsers.add_parser("doctor", help="report which engines are available")
    doctor.set_defaults(func=_cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValueError as exc:
        # A bad --engines name should fail loudly rather than silently analysing with
        # fewer engines than the caller asked for.
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
