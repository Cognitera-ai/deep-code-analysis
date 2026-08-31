"""The output frame and its writers.

Five tables come out of a run (§6.1 of the spec), and they are separate for reasons that
each cost someone a rewrite:

* ``metrics`` — one row per fragment. The main table.
* ``functions`` — per-function detail. Separate because collapsing per-function metrics to
  mean/max/min is lossy (R-07) and throwing the detail away entirely would be worse.
* ``embeddings`` — the wide matrix. Separate because three models at 768–1024 dimensions
  would otherwise swamp a table of ~150 scalar columns (R-14).
* ``provenance`` — one envelope per run.
* ``degradations`` — every failure that was degraded rather than raised (R-20). Without
  this table an engine that broke looks exactly like a corpus where the metric does not
  apply.

Parquet is authoritative for round-tripping (R-18): CSV cannot distinguish an empty string
from a null, nor an int column with nulls from a float column, and both distinctions matter
here. CSV is still written because it is what a researcher opens.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from .core import FragmentResult
from .provenance import Provenance
from .schema import IDENTITY_COLUMNS


@dataclass(slots=True)
class MetricFrame:
    """The result of analysing a batch."""

    results: list[FragmentResult]
    provenance: Provenance | None = None
    columns: Sequence[str] | None = None

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self):
        return iter(self.results)

    # ── tables ──────────────────────────────────────────────────────────────────────

    def metrics(self) -> pd.DataFrame:
        """One row per fragment, columns in fixed schema order.

        Reindexing against the declared column list is what enforces R-13: a run where an
        engine was unavailable produces the same columns as one where it was not, so two
        frames concatenate without alignment surprises.
        """
        rows = [r.as_row() for r in self.results]
        frame = pd.DataFrame(rows)
        if self.columns is not None:
            ordered = list(IDENTITY_COLUMNS) + list(self.columns)
            frame = frame.reindex(columns=ordered)
        return frame

    def functions(self) -> pd.DataFrame:
        """Per-function detail, long format (R-07)."""
        rows = [row for r in self.results for row in r.functions]
        return pd.DataFrame(rows)

    def degradations(self) -> pd.DataFrame:
        """Every degraded failure (R-20)."""
        rows = [d.as_row() for r in self.results for d in r.degradations]
        return pd.DataFrame(rows, columns=["engine", "fragment_id", "kind", "detail"])

    def provenance_dict(self) -> dict[str, Any]:
        return self.provenance.as_dict() if self.provenance else {}

    # ── summaries ───────────────────────────────────────────────────────────────────

    def null_rates(self) -> pd.Series:
        """Share of nulls per metric column.

        Not a diagnostic afterthought: the null rate per engine is itself a research datum.
        It is exactly what revealed that radon's maintainability index was a constant for
        three quarters of a corpus, a fact none of the published studies using that engine
        reported.
        """
        frame = self.metrics().drop(columns=list(IDENTITY_COLUMNS), errors="ignore")
        if frame.empty:
            return pd.Series(dtype=float)
        return frame.isna().mean().sort_values(ascending=False)

    def divergence_summary(self) -> pd.DataFrame:
        """Per comparable metric: how often the engines disagreed, and by how much.

        This is the table the conformance suite's divergence matrix is built from, and the
        one worth looking at first on any new corpus.
        """
        frame = self.metrics()
        rows = []
        for column in frame.columns:
            if not column.endswith("__divergent"):
                continue
            key = column[: -len("__divergent")]
            ratio_col = f"{key}__delta_ratio"
            flags = frame[column].dropna()
            ratios = frame[ratio_col].dropna() if ratio_col in frame else pd.Series(dtype=float)
            if flags.empty and ratios.empty:
                continue
            rows.append(
                {
                    "metric": key,
                    "compared": int(len(flags)),
                    "divergent": int(flags.sum()) if len(flags) else 0,
                    "divergent_rate": round(float(flags.mean()), 4) if len(flags) else None,
                    "ratio_median": round(float(ratios.median()), 4) if len(ratios) else None,
                    "ratio_max": round(float(ratios.max()), 4) if len(ratios) else None,
                }
            )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows).sort_values(
            "divergent_rate", ascending=False, ignore_index=True
        )

    # ── writers ─────────────────────────────────────────────────────────────────────

    def to_csv(self, directory: str | Path, *, prefix: str = "dca") -> dict[str, Path]:
        """Write every table as CSV, plus the provenance envelope as JSON.

        Provenance is JSON even in CSV mode: it is a nested document, and flattening it
        into a one-row table would lose the structure that makes it auditable.
        """
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        for name, table in self._tables().items():
            if table is None or table.empty:
                continue
            path = out / f"{prefix}_{name}.csv"
            table.to_csv(path, index=False)
            written[name] = path
        path = out / f"{prefix}_provenance.json"
        path.write_text(json.dumps(self.provenance_dict(), indent=2), encoding="utf-8")
        written["provenance"] = path
        return written

    def to_parquet(self, directory: str | Path, *, prefix: str = "dca") -> dict[str, Path]:
        """Write every table as Parquet. Authoritative for round-tripping (R-18)."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        written: dict[str, Path] = {}
        for name, table in self._tables().items():
            if table is None or table.empty:
                continue
            path = out / f"{prefix}_{name}.parquet"
            table.to_parquet(path, index=False)
            written[name] = path
        path = out / f"{prefix}_provenance.json"
        path.write_text(json.dumps(self.provenance_dict(), indent=2), encoding="utf-8")
        written["provenance"] = path
        return written

    def _tables(self) -> dict[str, pd.DataFrame]:
        return {
            "metrics": self.metrics(),
            "functions": self.functions(),
            "degradations": self.degradations(),
        }
