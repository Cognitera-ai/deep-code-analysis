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
        metrics = frame.metrics()
        with_pandas_width(metrics)

    degradations = frame.degradations()
    if not degradations.empty:
        print(f"\n{len(degradations)} degradation(s) recorded:", file=sys.stderr)
        for _, row in degradations.iterrows():
            print(f"  {row['engine']}: {row['detail']}", file=sys.stderr)

    if args.summary:
        summary = frame.divergence_summary()
        if not summary.empty:
            print("\nDivergence between engines:")
            print(summary.to_string(index=False))
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


def _cmd_doctor(args: argparse.Namespace) -> int:
    """Report engine availability. Exits non-zero if a default engine is missing."""
    adapters = build_adapters(None, include_optional=True)
    missing_default = False
    default_names = {a.name for a in build_adapters(None)}

    print(f"dca {__version__}\n")
    print(f"{'engine':<12} {'path':<11} {'status':<14} version")
    print("-" * 56)
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
        version = adapter.version or "-"
        print(f"{adapter.name:<12} {adapter.path:<11} {status:<14} {version}")

    from . import embeddings

    print(f"\nembeddings extra: {'available' if embeddings.is_available() else 'not installed'}")

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
