# ADR-0003 — MIT licence, and copyleft excluded from the import tree

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Several relevant tools in the domain are copyleft:

| Tool | Licence | What it would contribute |
|---|---|---|
| `pylint` | **GPLv2+** | The broadest smell catalogue in Python |
| `cohesion` | **GPLv3** | Class cohesion |
| `prospector` | **GPL-2.0** | Findings aggregation |
| `cloc` | **GPL v2** | Line counting |
| OpenStaticAnalyzer | **EUPL v1.2** | Cohesion, coupling, inheritance |

Importing any of them from a library would, with high probability, force the entire package
to be copyleft.

The project is research software with no commercial interest, so accepting the GPL would
have been defensible. But on reviewing what each one actually contributes, **it turned out
nothing had to be conceded**: `pyscn` (MIT) provides canonical LCOM4 — better than
`cohesion`'s non-standard percentage variant — and additionally covers CBO and dead code;
and `pylint`'s contribution to a *metric vector* was always weak, because it is a findings
tool, not a measurement tool.

## Decision

**The package is MIT licensed.** No copyleft dependency enters the import tree.

| Path | Packages | Licences |
|---|---|---|
| Direct `import` | `radon`, `lizard`, `complexipy`, `ast` (stdlib) | MIT, MIT, MIT, PSF |
| Subprocess | `pyscn`, `vulture`, `bandit` | MIT, MIT, Apache-2.0 |
| Optional extra | `transformers`, `torch` + weights | Apache-2.0 |

**Excluded:** `pylint` (except as a subprocess extra,
[ADR-0011](0011-pylint-as-subprocess-extra.md)), `cohesion`, `prospector`, `cloc`,
`OpenStaticAnalyzer`, and `multimetric` (by [ADR-0005](0005-drop-multimetric.md), not for
licensing — it is Zlib, permissive).

## Consequences

- The package can be used and redistributed without friction, including inside other
  academic artifacts under different licences.
- We give up pylint's smell catalogue as a first-class metric.
- **Operating rule for the building agent:** for any new dependency, verify the licence
  *before* writing the adapter. A GPL dependency in the import tree is a blocking defect,
  not a style preference.

## Note on `lizard`

lizard's `LICENSE.txt` contains the full MIT text. Its PyPI classifier says `Freeware`. The
repository's actual licence is treated as authoritative, and the discrepancy is recorded as
a metadata inconsistency to report upstream.
