"""Rich terminal output, with a plain-text fallback that is never worse than informative.

Two rules shape this module.

**The tool must work without it.** `rich` lives behind the `tui` extra, so every function
here degrades to plain text when it is absent. A research tool that refuses to run because
a presentation library is missing has its priorities backwards — the numbers are the
product, the colour is a convenience.

**Colour carries meaning or it is not used.** Divergence is the thing this package exists
to surface, and it is genuinely visual: `radon: 0` beside `lizard: 139.0` in contrasting
colour communicates in a second what a CSV column never communicates at all. Everywhere
else, colour is restrained on purpose — if every row is coloured, no row is emphasised.
"""

from __future__ import annotations

from typing import Any

try:  # pragma: no cover - trivially environment-dependent
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    RICH = True
except ImportError:  # pragma: no cover
    RICH = False
    Console = Table = Text = None  # type: ignore[assignment,misc]


#: Divergence severity thresholds, in ratio terms. These are presentation bands, not
#: findings — the schema's own `__divergent` flag is the measurement.
_SEVERE = 5.0
_NOTABLE = 1.5


def console(**kwargs: Any):
    """A Rich console, or None when the extra is absent."""
    return Console(**kwargs) if RICH else None


def _fmt(value: Any) -> str:
    """Render one metric value the way a reader wants to see it.

    Null and zero are printed differently on purpose. They mean different things in this
    schema — zero is a measurement, null is an absence — and a table that renders both as
    an empty cell erases the distinction the whole package is built around.
    """
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _severity(ratio: float | None, divergent: bool | None) -> str:
    """Colour for a divergence, by how far apart the engines are."""
    if divergent is not True:
        return "green"
    if ratio is None:
        # Zero versus non-zero: no ratio exists, and it is the strongest disagreement
        # there is — one engine says absent, another says present.
        return "bold magenta"
    if ratio >= _SEVERE:
        return "bold red"
    if ratio >= _NOTABLE:
        return "yellow"
    return "green"


def print_doctor(rows: list[dict[str, Any]], version: str, embeddings: bool) -> None:
    """Engine availability. The answer to 'why is this column empty?'."""
    if not RICH:
        print(f"dca {version}\n")
        print(f"{'engine':<12} {'path':<11} {'status':<14} version")
        print("-" * 56)
        for r in rows:
            print(f"{r['name']:<12} {r['path']:<11} {r['status']:<14} {r['version']}")
        print(f"\nembeddings extra: {'available' if embeddings else 'not installed'}")
        return

    c = Console()
    table = Table(title=f"dca {version} · engines", title_style="bold", header_style="bold")
    table.add_column("engine", style="cyan", no_wrap=True)
    table.add_column("path")
    table.add_column("status")
    table.add_column("version", style="dim")

    styles = {"available": "green", "MISSING": "bold red", "optional, off": "dim"}
    for r in rows:
        table.add_row(
            r["name"],
            r["path"],
            Text(r["status"], style=styles.get(r["status"], "")),
            r["version"],
        )
    c.print(table)
    state = "[green]available[/green]" if embeddings else "[dim]not installed[/dim]"
    c.print(f"embeddings extra: {state}")


def print_divergence(rows: list[dict[str, Any]]) -> None:
    """Where the engines disagreed, and by how much. The headline view."""
    if not rows:
        return
    if not RICH:
        print(f"\n{'metric':<32} {'compared':>8} {'divergent':>9} {'median':>9} {'max':>10}")
        for r in rows:
            print(
                f"{r['metric']:<32} {r['compared']:>8} {r['divergent']:>9} "
                f"{_fmt(r['ratio_median']):>9} {_fmt(r['ratio_max']):>10}"
            )
        return

    table = Table(
        title="engine divergence",
        caption=(
            "magenta = one engine reports zero where another does not; "
            "no ratio can express that"
        ),
        title_style="bold",
        header_style="bold",
        caption_style="dim italic",
    )
    table.add_column("metric", style="cyan", no_wrap=True)
    table.add_column("compared", justify="right")
    table.add_column("divergent", justify="right")
    table.add_column("rate", justify="right")
    table.add_column("median ratio", justify="right")
    table.add_column("max ratio", justify="right")

    for r in rows:
        rate = r.get("divergent_rate")
        median = r.get("ratio_median")
        # A metric flagged divergent with no ratio at all is the zero-versus-nonzero case.
        style = _severity(median, bool(rate))
        if rate and median is None:
            style = "bold magenta"
        table.add_row(
            r["metric"],
            str(r["compared"]),
            Text(str(r["divergent"]), style=style),
            Text(f"{rate:.0%}" if rate is not None else "—", style=style),
            Text(_fmt(median), style=style),
            Text(_fmt(r.get("ratio_max")), style=style),
        )
    Console().print(table)


def print_fragment(fragment_id: str, by_metric: dict[str, dict[str, Any]]) -> None:
    """One fragment, its metrics grouped so that disagreements sit side by side.

    Grouping by metric rather than by engine is the whole point: an engine-major table
    hides disagreement across columns, while a metric-major one puts the two readings on
    the same row where the eye finds them.
    """
    if not RICH:
        print(f"\n{fragment_id}")
        for key, readings in sorted(by_metric.items()):
            values = "  ".join(f"{e}={_fmt(v)}" for e, v in readings.items() if e != "_meta")
            print(f"  {key:<34} {values}")
        return

    c = Console()
    engines = sorted({e for r in by_metric.values() for e in r if e != "_meta"})
    table = Table(title=fragment_id, title_style="bold cyan", header_style="bold")
    table.add_column("metric", style="cyan", no_wrap=True)
    for engine in engines:
        table.add_column(engine, justify="right")
    table.add_column("", width=3)  # divergence marker

    for key in sorted(by_metric):
        readings = by_metric[key]
        meta = readings.get("_meta", {})
        style = _severity(meta.get("ratio"), meta.get("divergent"))
        marker = ""
        if meta.get("divergent"):
            marker = "!!" if meta.get("ratio") is None or meta["ratio"] >= _SEVERE else "!"
        cells = [Text(_fmt(readings.get(e)), style=style if marker else "") for e in engines]
        table.add_row(key, *cells, Text(marker, style=style))
    c.print(table)


def _short(identifier: str, limit: int = 40) -> str:
    """A fragment identifier short enough to read: the filename and its parent."""
    parts = identifier.replace("\\", "/").split("/")
    short = "/".join(parts[-2:]) if len(parts) > 1 else identifier
    return short if len(short) <= limit else "…" + short[-(limit - 1):]


def print_overview(rows: list[dict[str, Any]], total_columns: int) -> None:
    """A readable stdout view of an analysis.

    Deliberately not the whole frame. Printing 138 columns to a terminal produces something
    nobody can read and that no tool can consume either — the full data belongs in a file,
    which is what ``--out`` is for. What a person wants on screen is the shape of the
    result and where to look next, so this shows size, complexity and how many engines
    disagreed, and says where the rest went.
    """
    if not RICH:
        print(f"{'fragment':<42} {'lloc':>6} {'cc':>6} {'disagree':>9}")
        for r in rows:
            print(
                f"{_short(r['fragment'], 42):<42} {_fmt(r['lloc']):>6} "
                f"{_fmt(r['cc']):>6} {r['divergent']:>9}"
            )
        print(f"\n{len(rows)} fragments, {total_columns} metric columns. --out writes them all.")
        return

    c = Console()
    table = Table(header_style="bold", expand=False)
    # A width cap on the identifier rather than letting it consume the row: full paths are
    # long, the informative part is the tail, and headers truncated to "en… di…" tell the
    # reader nothing.
    table.add_column("fragment", style="cyan", no_wrap=True, max_width=40)
    table.add_column("valid", justify="center", width=7)
    table.add_column("lloc", justify="right", width=6)
    table.add_column("cc", justify="right", width=6)
    table.add_column("disagree", justify="right", width=9)

    for r in rows:
        count = r["divergent"]
        style = "bold red" if count >= 5 else "yellow" if count else "dim"
        table.add_row(
            _short(r["fragment"]),
            Text("ok", style="green") if r["valid"] else Text("invalid", style="red"),
            _fmt(r["lloc"]),
            _fmt(r["cc"]),
            Text(str(count), style=style),
        )
    c.print(table)
    c.print(
        f"[dim]{len(rows)} fragments · {total_columns} metric columns · "
        "[/dim][bold]--out[/bold][dim] writes every column; "
        "[/dim][bold]--summary[/bold][dim] shows where engines disagreed[/dim]"
    )
