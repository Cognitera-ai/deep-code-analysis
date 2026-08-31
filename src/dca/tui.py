"""An interactive view of engine disagreement — `dca explore`.

Why this exists when the rest of the package deliberately does not have a UI: exploring
divergence is genuinely exploratory. "Where do the engines disagree most, and what does
that file look like?" is a question you follow rather than answer once, and following it in
a CSV means grepping, sorting and losing your place. Everything else this package does —
measure a corpus, write a Parquet, hand it to pandas — is better served by a file than by a
screen, and deliberately has no TUI.

The scope is therefore narrow on purpose. This is not a general interface over the package.
It is one question, answered well.

Requires the `tui` extra. Without it, `dca explore` says so and exits rather than failing
with an ImportError, because a missing optional dependency is a configuration state, not a
crash.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:  # pragma: no cover - environment-dependent
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal, Vertical
    from textual.widgets import DataTable, Footer, Header, Static

    TEXTUAL = True
except ImportError:  # pragma: no cover
    TEXTUAL = False
    App = object  # type: ignore[assignment,misc]
    ComposeResult = Any  # type: ignore[misc]


class TuiUnavailableError(RuntimeError):
    """The `tui` extra is not installed."""


def is_available() -> bool:
    """Whether the TUI can run here. Never raises."""
    return TEXTUAL


#: Presentation bands for how far apart two engines are. Not findings — the schema's own
#: `__divergent` flag is the measurement; these only decide a colour.
SEVERE = 5.0
NOTABLE = 1.5


def _severity(ratio: float | None, divergent: bool | None) -> tuple[str, str]:
    """(label, colour) for one metric's disagreement."""
    if divergent is not True:
        return "agree", "green"
    if ratio is None:
        # One engine reports the quantity absent, another reports it present. There is no
        # ratio for that, and it is stronger than any ratio could express.
        return "absent/present", "magenta"
    if ratio >= SEVERE:
        return f"{ratio:.1f}x", "red"
    if ratio >= NOTABLE:
        return f"{ratio:.1f}x", "yellow"
    return f"{ratio:.2f}x", "green"


if TEXTUAL:

    class DivergenceExplorer(App):
        """Fragments on the left, their engine disagreements on the right."""

        CSS = """
        Screen { layout: vertical; }
        #panes { height: 1fr; }
        #fragments { width: 42%; border: round $primary; }
        #detail { width: 1fr; border: round $secondary; }
        #summary { height: auto; padding: 0 1; color: $text-muted; }
        DataTable { height: 1fr; }
        """

        BINDINGS = [
            Binding("q", "quit", "quit"),
            Binding("d", "toggle_divergent", "only divergent"),
            Binding("r", "refresh_detail", "refresh"),
        ]

        def __init__(self, frame, title: str = "divergence") -> None:
            super().__init__()
            self.frame = frame
            self._title = title
            self.only_divergent = True

        # ── layout ──────────────────────────────────────────────────────────────────

        def compose(self) -> ComposeResult:
            yield Header(show_clock=False)
            yield Static(self._summary_line(), id="summary")
            with Horizontal(id="panes"):
                with Vertical(id="fragments"):
                    yield DataTable(id="fragment_table", cursor_type="row")
                with Vertical(id="detail"):
                    yield DataTable(id="detail_table", cursor_type="row")
            yield Footer()

        def on_mount(self) -> None:
            self.title = f"dca · {self._title}"
            self.sub_title = "engine disagreement"

            fragments = self.query_one("#fragment_table", DataTable)
            fragments.add_columns("fragment", "divergent")
            metrics = self.frame.metrics()
            for _, row in metrics.iterrows():
                count = self._divergence_count(row)
                # Sorting is by disagreement, so the interesting rows are the first ones
                # you see rather than something you have to hunt for.
                fragments.add_row(
                    str(row["fragment_id"])[-46:],
                    str(count),
                    key=str(row["fragment_id"]),
                )

            detail = self.query_one("#detail_table", DataTable)
            detail.add_columns("metric", "engine", "value", "vs")
            if metrics.shape[0]:
                self._show(str(metrics.iloc[0]["fragment_id"]))

        # ── behaviour ───────────────────────────────────────────────────────────────

        def on_data_table_row_highlighted(self, event) -> None:
            if event.data_table.id == "fragment_table" and event.row_key is not None:
                self._show(str(event.row_key.value))

        def action_toggle_divergent(self) -> None:
            self.only_divergent = not self.only_divergent
            self.action_refresh_detail()

        def action_refresh_detail(self) -> None:
            table = self.query_one("#fragment_table", DataTable)
            if table.row_count:
                key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key
                self._show(str(key.value))

        # ── rendering ───────────────────────────────────────────────────────────────

        def _summary_line(self) -> str:
            summary = self.frame.divergence_summary()
            if summary.empty:
                return "no comparable metrics: only one engine emits each of these"
            worst = summary.iloc[0]
            return (
                f"{len(self.frame)} fragments · {len(summary)} comparable metrics · "
                f"worst: {worst['metric']} ({worst['divergent_rate']:.0%} divergent)"
            )

        def _divergence_count(self, row) -> int:
            from .schema import is_true

            return sum(1 for k, v in row.items() if k.endswith("__divergent") and is_true(v))

        def _show(self, fragment_id: str) -> None:
            from .schema import is_true, split_column

            metrics = self.frame.metrics()
            match = metrics[metrics["fragment_id"].astype(str) == fragment_id]
            if match.empty:
                return
            row = match.iloc[0]

            detail = self.query_one("#detail_table", DataTable)
            detail.clear()

            grouped: dict[str, dict[str, Any]] = {}
            for column, value in row.items():
                key, engine = split_column(str(column))
                if engine in (None, "delta_ratio", "divergent"):
                    continue
                grouped.setdefault(key, {})[engine] = value

            for key in sorted(grouped):
                readings = {e: v for e, v in grouped[key].items() if v is not None}
                if len(readings) < 2:
                    continue  # nothing to compare: not a disagreement, just one opinion
                divergent = is_true(row.get(f"{key}__divergent"))
                ratio = row.get(f"{key}__delta_ratio")
                if self.only_divergent and not divergent:
                    continue
                label, colour = _severity(
                    None if ratio is None or ratio != ratio else float(ratio),
                    divergent,
                )
                for i, (engine, value) in enumerate(sorted(readings.items())):
                    shown = f"{value:.4g}" if isinstance(value, float) else str(value)
                    detail.add_row(
                        key if i == 0 else "",
                        engine,
                        f"[{colour}]{shown}[/{colour}]",
                        f"[{colour}]{label}[/{colour}]" if i == 0 else "",
                    )


def explore(frame, title: str = "divergence") -> None:
    """Open the explorer over an analysed frame."""
    if not TEXTUAL:
        raise TuiUnavailableError(
            "the interactive explorer needs the tui extra: "
            'pip install "deep-code-analysis[tui]"'
        )
    DivergenceExplorer(frame, title=title).run()


def explore_paths(paths: list[str], *, engines: list[str] | None = None) -> None:
    """Analyse some files and open the explorer over the result."""
    from .core import Analyser

    sources: dict[str, str] = {}
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for file in sorted(path.rglob("*.py")):
                sources[str(file)] = file.read_text(encoding="utf-8", errors="replace")
        elif path.is_file():
            sources[str(path)] = path.read_text(encoding="utf-8", errors="replace")

    if not sources:
        raise FileNotFoundError("no Python files found in the given paths")

    frame = Analyser(engines=engines).analyse_many(sources)
    explore(frame, title=", ".join(paths)[:60])
