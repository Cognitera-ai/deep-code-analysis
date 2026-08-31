# Architecture Decision Records

Each file documents one decision taken while designing the package: the context that forced
it, the decision itself, its consequences, and the alternatives rejected.

| # | Decision | Core idea |
|---|---|---|
| [0001](0001-delegate-do-not-reimplement.md) | Delegate, do not reimplement | No metric is rewritten; the package contributes schema, provenance and divergence |
| [0002](0002-scope-v1-python-only.md) | v1 scope: Python only | Multi-language declared as later work, not as an omission |
| [0003](0003-mit-licence-and-copyleft-exclusion.md) | MIT, no copyleft imported | It turned out nothing had to be conceded: the permissive substitutes are better |
| [0004](0004-no-canonical-engine.md) | No canonical engine | radon and lizard side by side plus their delta; the bare column name is forbidden |
| [0005](0005-drop-multimetric.md) | Drop multimetric | Its CC is not McCabe and its MI is unbounded; rejecting it produced publishable evidence |
| [0006](0006-oo-metrics-via-pyscn.md) | OO metrics via pyscn | Reverses a 2024 premise that pyscn invalidated; removes the largest first-party block |
| [0007](0007-provenance-is-mandatory.md) | Provenance is mandatory | Never a naked number; no tool in the domain does this |
| [0009](0009-three-embedding-models.md) | Three embedding models | UniXcoder justified by comparison, not assumed; always behind an extra |
| [0010](0010-conformance-characterises-not-certifies.md) | Conformance ≠ correctness | There is no oracle; the suite reproduces and characterises, it does not certify |
| [0011](0011-pylint-as-subprocess-extra.md) | pylint out of the import tree | Optional subprocess extra; grouped by category, never by message code |
| [0012](0012-adapter-contract.md) | A single adapter contract | What allows adapters to be built in parallel and dead engines retired |
| [0013](0013-degrade-do-not-abort.md) | Degrade, never abort | Null ≠ zero; three real incidents sit behind each rule |
| [0014](0014-public-repository-from-day-one.md) | ~~Public from day one~~ | **Superseded by 0017.** Its JOSS analysis still governs the timing |
| [0015](0015-documentation-generated-from-schema.md) | Generated documentation | An out-of-date catalogue is a CI failure, not a pending task |
| [0016](0016-english-throughout.md) | English throughout | Supersedes an earlier Spanish/English split |
| [0017](0017-private-until-ready.md) | ~~Private until ready~~ | **Superseded by 0018.** Its argument is why the parity suite exists |
| [0018](0018-public-repository.md) | The repository is public | Renamed to `deep-code-analysis`; the obligations of being public are now live |

## Format

Title, status, date, context, decision, consequences, alternatives rejected. One decision
per file. Decisions are not edited when they change: they are marked superseded and a new
record is written that reverses them, as [ADR-0006](0006-oo-metrics-via-pyscn.md),
[ADR-0016](0016-english-throughout.md) and [ADR-0017](0017-private-until-ready.md) do.
