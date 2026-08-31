# Technical Specification

**Build document for `deep-code-analysis` v1.**

> **This document is written to be built from autonomously.** There is no human in the loop
> during construction. Every ambiguity that would normally trigger a question has been
> pre-decided in §4, with its reasoning, so the building agent never has to guess or wait.
>
> **Read §4 (Rulings), §9 (Conformance) and §13 (Acceptance criteria) before writing any
> code.** They are, respectively: what has been decided for you, how you know you got it
> right, and how you know you are finished.
>
> Background reading, in order of usefulness: [`motivation.md`](motivation.md) (why this
> exists and what the evidence is), [`adr/`](adr/) (why each decision was made),
> [`tool-landscape.md`](tool-landscape.md) (what else exists).
>
> Everything in this repository is in English — code, comments, docs, identifiers
> ([ADR-0016](adr/0016-english-throughout.md)).

---

## 1. Purpose and non-goals

### 1.1 Purpose

Emit, for a fragment of Python source code, every metric the community currently knows how
to compute, in **one tabular schema**, with **verifiable provenance attached to every
value**, and with **inter-engine divergence made explicit rather than hidden**.

### 1.2 Non-goals for v1

These are decisions, not omissions. Do not implement them, and do not "helpfully" add them.

| Non-goal | Reason |
|---|---|
| Languages other than Python | [ADR-0002](adr/0002-scope-v1-python-only.md) |
| Reimplementing any metric algorithm | [ADR-0001](adr/0001-delegate-do-not-reimplement.md) |
| Resolving which engine is "right" | [ADR-0004](adr/0004-no-canonical-engine.md) |
| Any copyleft dependency in the import tree | [ADR-0003](adr/0003-mit-licence-and-copyleft-exclusion.md) |
| Dimensionality reduction, clustering, plotting | Out of scope; the package emits vectors, the researcher analyses them |
| DIT and RFC | No Python engine emits them; v2 roadmap ([ADR-0006](adr/0006-oo-metrics-via-pyscn.md)) |
| A findings/linting report | This is a measurement tool, not a linter |

### 1.3 Unit of analysis

One **code fragment**: a string of Python source. Not a file, not a repository. Fragments
come from LLM responses, so they may be flat scripts, single functions, or invalid Python.

The schema is **one row per fragment**. Per-function and per-class metrics are aggregated to
the fragment (§4, ruling R-07) with the per-function detail available through a separate
long-format accessor.

---

## 2. Frozen dependency set

Pin exact versions. Ranges break the conformance suite's determinism
([ADR-0010](adr/0010-conformance-characterises-not-certifies.md)).

### 2.1 Runtime, import path

| Package | Version | Licence | Provides |
|---|---|---|---|
| `radon` | `==6.0.1` | MIT | raw size, MI, CC, Halstead |
| `lizard` | `>=1.24.0,<2` | MIT | per-function CCN/NLOC/tokens/params, Halstead (`-Ehalstead`) |
| `complexipy` | `>=7.0.1,<8` | MIT | cognitive complexity |
| `ast` | stdlib | PSF | structural metrics |

`lizard` needs `>=1.24.0` specifically: the Halstead extension does not exist in 1.23.x.
Verify this at import time and fail loudly if a lower version is installed.

### 2.2 Runtime, subprocess path

Never imported. Invoked as binaries, output consumed as JSON.

| Tool | Version | Licence | Provides |
|---|---|---|---|
| `pyscn` | pinned exact | MIT | CBO, LCOM4, CFG nodes/edges, nesting depth, dead code, APTED clones |
| `vulture` | `>=2.16` | MIT | dead code (heuristic) |
| `bandit` | pinned exact | Apache-2.0 | security smells |

`vulture` and `bandit` are pip-installable and *could* be imported; they are deliberately
kept on the subprocess path anyway so that all findings-style tools share one integration
shape and none of them can crash the host process.

### 2.3 Optional extras

| Extra | Packages | Provides |
|---|---|---|
| `embeddings` | `torch`, `transformers` | The three models of [ADR-0009](adr/0009-three-embedding-models.md) |
| `pylint` | `pylint` (subprocess only) | Global score + per-category counts ([ADR-0011](adr/0011-pylint-as-subprocess-extra.md)) |
| `conformance` | `ast-metrics`, `cognitive_complexity` | Oracles for the divergence suite only |

`torch` must come from the CPU wheel index by default. The CUDA build is multiple gigabytes
and is not needed for encoders this size.

### 2.4 Forbidden

`pylint` as an import · `cohesion` · `prospector` · `cloc` · `OpenStaticAnalyzer` ·
`multimetric` (any use, including as an oracle — see
[ADR-0005](adr/0005-drop-multimetric.md)).

---

## 3. Master metric catalogue

**This section defines the intent. The authoritative catalogue is generated from the
adapters' declarations** ([ADR-0015](adr/0015-documentation-generated-from-schema.md)); this
table is what the generated catalogue must cover.

Column naming is `{metric}__{engine}` without exception ([ADR-0004](adr/0004-no-canonical-engine.md)).

### 3.1 Size — engine: radon

`lloc`, `sloc`, `comments`, `single_comments`, `multi_line_comments`, `blank_lines`,
`total_lines`.

Radon's own invariant `sloc + blank + multi + single_comments == loc` must hold; assert it in
tests.

### 3.2 Cyclomatic complexity — engines: radon, lizard, pyscn

`cyclomatic_complexity_mean`, `cyclomatic_complexity_max`, `cyclomatic_complexity_module`,
`cc_imputed_module_level` (flag).

**Known-good:** radon and lizard agree exactly on 99.2 % of a real LLM corpus, differences
never exceeding ±1 (`motivation.md` §2.7). Divergence threshold for the flag: any difference.

**Module-level imputation (ruling R-04).** When a fragment has no `def`/`class`, radon's
per-block CC list is empty. Do not emit null: the module body *is* a block, and McCabe's
number for a straight-line script is 1, plus one per module-level branch. Use
`ComplexityVisitor.complexity` and set `cc_imputed_module_level = 1`.

Rationale, and this matters: leaving it null makes the missingness itself a treatment
effect, because whether code defines a function is a property of whatever produced it. Any
analysis restricted to "rows where CC exists" would silently condition on that. The flag
keeps the imputed and measured populations separable so a study can report them apart.

### 3.3 Halstead — engines: radon, lizard

`halstead_h1`, `halstead_h2`, `halstead_n1`, `halstead_n2`, `halstead_vocabulary`,
`halstead_length`, `halstead_volume`, `halstead_difficulty`, `halstead_effort`,
`halstead_time`, `halstead_bugs`.

**This is the family where the engines break down.** Both engines are emitted, plus
`halstead_volume__delta_ratio` and `halstead_volume__divergent`.

Two documented pathologies the adapters must expose rather than smooth over:

- **radon is blind to most operators.** Its `HalsteadVisitor` implements only `visit_BinOp`,
  `visit_UnaryOp`, `visit_BoolOp`, `visit_AugAssign`, `visit_Compare`. Assignments, calls,
  attribute access, subscripting, `IfExp` and control-flow keywords are not operators to it.
  Measured consequence: 70 % zeros on a real LLM corpus, of which **99.7 % are blindness, not
  real absence** (`motivation.md` §2.4).
- **lizard measures only inside functions.** For flat scripts it returns nothing. It is not a
  drop-in replacement (`motivation.md` §2.5).

Emit `halstead_volume__radon_is_zero_but_lizard_is_not` as an explicit boolean. It is the
single most informative column in the divergence analysis.

### 3.4 Maintainability Index — engine: radon

`maintainability_index`, `maintainability_index__saturated` (flag).

**The flag is mandatory, not optional.** radon's `mi_compute` returns exactly 100.0 through
two distinct paths: a short-circuit when Halstead volume or SLOC is ≤ 0, and an upper clamp.
Measured: about 20 % saturation over installed open-source Python. A consumer reading this
column without the flag is reading a constant and will not know it.

Set the flag when the returned value is exactly 100.0, and record which path produced it.

### 3.5 Per-function metrics — engine: lizard

`avg_token_count`, `avg_param_count`, `avg_function_length`, `max_nesting_depth`, plus max
and min variants per ruling R-07.

Do **not** use lizard's `fan_in`/`fan_out`: the fields exist but always return 0.
Do **not** use the `-ENS` extension: its counter leaks across functions and files and depends
on invocation order (`motivation.md` §2.6). Use `max_nesting_depth` from the base analysis.

### 3.6 Cognitive complexity — engines: complexipy, pyscn

`cognitive_complexity_mean`, `cognitive_complexity_max`, plus the divergence pair.
The two engines are known to disagree (15 vs 16 on the same method); that disagreement is a
measurement, not a bug to fix.

### 3.7 Structural AST — engine: this package (the one exception to ADR-0001)

`ast_depth`, `total_nodes`, `functiondef_count`, `classdef_count`, `return_count`,
`call_count`, `assign_count`, `loop_ratio`, `if_ratio`, `import_ratio`, `comprehension_count`,
`try_count`, `decorator_count`.

Ratios use `total_nodes` as denominator. **`ast_depth` must be computed iteratively** — the
recursive version raises `RecursionError` on valid deeply-nested generated code
([ADR-0013](adr/0013-degrade-do-not-abort.md)).

No public tool emits these; they are first-party and their definitions must be documented
inline, since there is no upstream to defer to.

### 3.8 OO design — engine: pyscn

`cbo_mean`, `cbo_max`, `lcom4_mean`, `lcom4_max`, `module_dependencies`,
`cfg_nodes`, `cfg_edges`, `nesting_depth`, `if_statements`, `loop_statements`,
`exception_handlers`.

Null for fragments with no classes — a semantic null, not a failure.

### 3.9 Smells — engines: vulture, bandit, (pylint, optional)

`dead_code_items` (vulture) · `security_issues_low/medium/high`, `security_confidence_*`
(bandit) · `pylint_score`, `pylint_convention/refactor/warning/error` (extra only).

**Never one column per pylint message code.** Category grouping only
([ADR-0011](adr/0011-pylint-as-subprocess-extra.md)).

Note that vulture and pyscn both detect dead code by different methods (heuristic vs CFG).
Emit both. Their disagreement is a divergence datum.

### 3.10 Embeddings — extra only

`dim_0 … dim_N` per model, in a separate wide matrix keyed by fragment id — **never inline in
the scalar schema**, which would make the main table thousands of columns wide.

---

## 4. Rulings

**These are decided. Do not re-litigate them, do not ask, do not "improve" them.** Each
carries its reasoning so you can apply it correctly in cases the ruling does not name
verbatim.

| # | Ruling | Reasoning |
|---|---|---|
| **R-01** | PyPI name `deep-code-analysis`; import name `dca` | Long import names get aliased anyway; pick the alias |
| **R-02** | Python `>=3.11` | `tomllib` in stdlib, and the `ast` grammar is stable enough |
| **R-03** | Every column is `{metric}__{engine}`. The bare metric name is **forbidden** | [ADR-0004](adr/0004-no-canonical-engine.md). A bare name invites the reader to assume there is one answer |
| **R-04** | Module-level CC is imputed, never null, with a flag | §3.2. Null missingness correlates with the treatment |
| **R-05** | Null ≠ zero, everywhere, with no exception | Zero is a measurement, null is an absence. Conflating them falsifies every downstream statistic |
| **R-06** | Invalid Python → all metrics null, row still emitted, `is_valid_python = False` | Dropping rows breaks 1:1 alignment with other vectors. Filter at analysis time, not capture time |
| **R-07** | Per-function metrics aggregate to the fragment as `mean`, `max`, `min`; per-function detail is available through a separate long-format API | One row per fragment is the schema contract. But throwing away the detail is lossy, so expose it separately |
| **R-08** | Divergence columns are computed by the core, never by an adapter | [ADR-0012](adr/0012-adapter-contract.md). Adapters must not know about each other |
| **R-09** | Divergence threshold for the `__divergent` flag: relative difference > 10 %, or one engine zero and the other not | Arbitrary but documented and configurable. The 10 % figure is a starting point, not a finding |
| **R-10** | Subprocess timeout: 30 s per fragment per tool. Memory cap: 1 GiB | Generous for an analysis tool; tight enough that one pathological fragment cannot stall a batch |
| **R-11** | Captured subprocess output is drained to EOF with a 10 MiB cap, discarding the excess | Never stop reading: the child blocks on a full pipe and a well-behaved program gets misreported as a timeout ([ADR-0013](adr/0013-degrade-do-not-abort.md)) |
| **R-12** | Versions are read from the running process via `importlib.metadata`, never from `pyproject.toml` | A floor specifier is re-resolved at install; reporting it would be a fabrication ([ADR-0007](adr/0007-provenance-is-mandatory.md)) |
| **R-13** | The scalar schema is fixed and non-conditional. Engines that did not run produce null columns, not absent ones | A varying schema makes concatenation across runs a minefield |
| **R-14** | Embeddings live in their own matrix, keyed by fragment id | 3 models × 768–1024 dims would swamp the scalar table |
| **R-15** | Schema version is semantic and independent of package version. Adding a column is minor; renaming or removing is major | Consumers pin against the schema, not the package |
| **R-16** | The metric catalogue is generated from adapter declarations; CI fails if it drifts | [ADR-0015](adr/0015-documentation-generated-from-schema.md) |
| **R-17** | The public API returns typed result objects, never bare dicts or bare floats | [ADR-0007](adr/0007-provenance-is-mandatory.md): no naked numbers |
| **R-18** | Output formats: CSV and Parquet. Parquet is authoritative for round-tripping (CSV loses types) | Both are needed; only one can be authoritative |
| **R-19** | An adapter never raises upward. It returns a typed failure | [ADR-0013](adr/0013-degrade-do-not-abort.md) |
| **R-20** | Every degradation is logged with engine, exception type and fragment id | A silent degradation is a defect |
| **R-21** | No network access at analysis time, except the first embedding-model download | Reproducibility. A metrics run that phones home is not a measurement |
| **R-22** | Dead code is emitted from both vulture and pyscn, never reconciled | Their disagreement is data |
| **R-23** | If `lizard < 1.24`, fail at import with a clear message | The Halstead extension does not exist below it; silently emitting nulls would look like real zeros |
| **R-24** | Tests use real fixture code, never mocked engine output | Mocking the engine hides exactly the class of bug this project exists to find |

---

## 5. Adapter contract

Every engine is integrated behind one interface ([ADR-0012](adr/0012-adapter-contract.md)).

```
Adapter
  name             -> str                  # engine identity, goes in every column name
  version          -> str | None           # resolved at runtime (R-12)
  path             -> "import" | "subprocess"
  is_available()   -> bool                 # never raises
  declared_metrics -> list[MetricSpec]     # feeds the generated catalogue (R-16)
  analyse(code)    -> AdapterResult        # never raises (R-19)

MetricSpec
  key, granularity ("file"|"function"|"class"), unit, dtype,
  valid_range, description, null_semantics

AdapterResult
  values: dict[str, float | int | None]
  failures: list[Degradation]
  raw: object | None                       # kept for the conformance suite only
```

Mandatory rules:

1. **No adapter writes to the schema.** It returns its vector; the core composes.
2. **No adapter imports another adapter.** Divergence is a core concern (R-08).
3. **The engine name goes in the column name.** Always.
4. **A broken engine is disabled without touching the rest.** `is_available()` returning
   `False` produces null columns, not a crash.

This is what makes the adapter phases parallelisable: an agent building the `bandit` adapter
never needs to know what the `radon` adapter is doing.

---

## 6. Output schema and versioning

### 6.1 Shape

| Table | Key | Contents |
|---|---|---|
| `metrics` | `fragment_id` | The scalar vector, one row per fragment |
| `functions` | `fragment_id`, `function_index` | Per-function detail (R-07) |
| `embeddings` | `fragment_id`, `model` | The wide matrix (R-14) |
| `provenance` | `run_id` | One envelope per export |
| `degradations` | `run_id`, `fragment_id` | Every failure that was degraded (R-20) |

### 6.2 Identity columns

`fragment_id`, `code_sha256`, `is_valid_python`, `language` (always `"python"` in v1, present
for forward compatibility per [ADR-0002](adr/0002-scope-v1-python-only.md)).

### 6.3 Versioning

Schema version is independent of package version (R-15). Every export stamps both.

---

## 7. Provenance envelope

Per [ADR-0007](adr/0007-provenance-is-mandatory.md). Required blocks:

```
analysis_chain   : {engine: version} for every engine that ran
interpreter      : python_version, implementation
package          : version, schema_version, schema_hash
environment      : os, arch, hostname_hash; gpu/cpu when embeddings ran
embeddings       : {model: {revision, device, dims}}
input            : fragment count, code_sha256 per fragment
generation       : OPTIONAL — model, temperature, top_p, top_k, seed, repetition_penalty
```

The `generation` block is what makes this package specifically useful for LLM research. It
is caller-supplied and optional; when absent, omit the block rather than emitting nulls.

Every field degrades to `None` rather than raising. Provenance capture must never be able to
fail an export.

---

## 8. Error and degradation policy

Per [ADR-0013](adr/0013-degrade-do-not-abort.md). Restating the operative rules because they
are the ones most often violated by a well-meaning implementation:

1. Null ≠ zero (R-05).
2. `ast_depth` iterative, never recursive.
3. Subprocess output drained past the cap, never buffered (R-11).
4. Every degradation logged (R-20).
5. One fragment's failure never affects another.

The three incidents behind these rules — `RecursionError` on valid nested code, OOM from
unbounded output capture, radon raising on exotic-but-parseable code — are documented in the
ADR. They are not hypothetical.

---

## 9. Conformance suite

Per [ADR-0010](adr/0010-conformance-characterises-not-certifies.md). **This is the project's
core deliverable, not its test folder.**

### 9.1 What it may and may not assert

**Valid:** "Reproduces radon 6.0.1 within ε over corpus C, and diverges from lizard 1.24.0 in
cases X, Y, Z for documented reasons R."

**Forbidden:** "The Halstead volume computed by this package is correct."

There is no oracle. Validating against radon and validating against lizard are mutually
incompatible goals.

### 9.2 Structure

1. **Reproduction tests.** For each delegated engine, the package returns exactly what the
   engine returns over the versioned corpus. This proves the adapter does not distort. Any
   difference is a bug in this package.
2. **Divergence matrix.** For each multi-engine metric, the distribution of inter-engine
   ratios over the corpus, with extreme cases named and preserved.
3. **Classification.** Each divergence labelled *specification difference* or *bug*. radon's
   Halstead blindness is the first; lizard's `-ENS` leak is the second.
4. **Golden files.** Versioned, regenerable by one command. A diff is the signal that an
   engine changed behaviour.

### 9.3 Corpus

Three tiers, all versioned in-repo:

| Tier | Content | Purpose |
|---|---|---|
| `minimal` | ~50 hand-written fragments, one per known pathology | Fast CI; each fragment documents the case it pins |
| `humaneval` | The 164 canonical solutions | External comparability with published literature |
| `generated` | A sample of real LLM output, including invalid and pathological fragments | The actual use case; where the interesting divergences live |

The `minimal` tier must include, at minimum, fragments that reproduce: radon Halstead = 0 with
non-trivial operator content; MI saturation via both paths; a flat script with no `def`; deeply
nested but valid code; a fragment that prints unboundedly; syntactically invalid code; a
fragment with classes for the OO metrics.

---

## 10. Public API and CLI

Keep the surface small and freeze it before writing the adapters.

```python
from dca import analyse, analyse_many

result = analyse(code)                    # -> FragmentResult (R-17)
result.metrics                            # typed, provenance-attached
result.provenance
result.degradations

frame = analyse_many(fragments)           # -> MetricFrame; .to_csv() / .to_parquet()

```

CLI: `dca analyse <path|-> [--format csv|parquet] [--engines ...] [--out ...]`,
`dca catalogue` (print the generated metric catalogue), `dca doctor` (report which engines are
available and at what version).

`dca doctor` matters more than it looks: with seven engines, "why is this column empty?" is
the most common user question, and it must be answerable in one command.

---

## 11. Packaging, extras and CI

- `uv` for dependency management; exact pins.
- Extras: `embeddings`, `pylint`, `conformance`, `all`.
- CI matrix: Python 3.11, 3.12, 3.13.
- CI jobs: lint (`ruff`), types, unit tests, conformance (`minimal` tier on every push;
  full corpus nightly), catalogue-drift check (R-16), licence check.
- **Licence check is a real CI job**, not a convention: it fails if any package in the import
  tree is copyleft ([ADR-0003](adr/0003-mit-licence-and-copyleft-exclusion.md)).

---

## 12. Generated documentation

Per [ADR-0015](adr/0015-documentation-generated-from-schema.md). The catalogue is generated
from `declared_metrics` across adapters, carries a do-not-edit header, and CI fails on drift.

---

## 13. Acceptance criteria

**The build is done when all of these are true.** This is the stop condition; without it an
autonomous agent polishes indefinitely.

| # | Criterion | How it is checked |
|---|---|---|
| A-01 | Every engine in §2 has an adapter satisfying §5 | Contract test parameterised over all adapters |
| A-02 | No copyleft package in the import tree | CI licence job |
| A-03 | No column is named without its engine suffix | Schema test asserting the naming rule (R-03) |
| A-04 | Every metric column has an identifiable producing engine | Schema walk test (ADR-0007) |
| A-05 | Reproduction tests pass for every delegated engine | Conformance §9.2.1 |
| A-06 | The divergence matrix is produced and its extreme cases are documented | Conformance §9.2.2 |
| A-07 | radon MI saturation is flagged, and the flag matches a recomputation | Test against the `minimal` corpus |
| A-08 | Invalid, pathological and unbounded-output fragments degrade without aborting | Test against the `minimal` corpus |
| A-09 | Null and zero are never conflated | Test asserting no zeros in columns whose engine failed |
| A-10 | The generated catalogue matches the adapters | CI drift job |
| A-11 | `dca doctor` correctly reports availability with an engine deliberately uninstalled | Integration test |
| A-12 | Every adapter reproduces its engine's own CLI over real code | `tests/conformance/test_engine_parity.py` |
| A-13 | Embeddings work with the extra installed and degrade cleanly without it | Two CI paths |
| A-14 | CSV and Parquet round-trip; Parquet preserves types | Round-trip test |
| A-15 | README, catalogue and API docs exist and are in English | Manual, at release |

---

## 14. Build phases and parallelism

| Phase | Content | Depends on | Parallel |
|---|---|---|---|
| 0 | Skeleton: package, schema, adapter contract, provenance, degradation, CLI stubs, CI | — | No |
| 1a | Adapters: radon, lizard, ast | 0 | **Yes** |
| 1b | Adapters: complexipy, pyscn | 0 | **Yes** |
| 1c | Adapters: vulture, bandit | 0 | **Yes** |
| 1d | Embeddings (3 models, lazy, batched) | 0 | **Yes** |
| 2 | Core composition: divergence columns, schema assembly, writers | 1a–1c | No |
| 3 | Conformance suite and corpus | 2 | No |
| 4 | Generated catalogue and docs | 2 | Partial |
| 5 | Robustness pass against the pathological corpus | 2 | No |
| 6 | Packaging, release, DOI | 3–5 | No |

Phases 1a–1d are the reason the adapter contract exists. They share only §5 and can be built
concurrently without coordination.

**Estimated total: ~20–28 agent sessions**, roughly 1.5 days of unattended wall-clock with the
adapter phases fanned out.

### Order of work within a phase

Write the contract test first, then the adapter. With seven engines of differing shapes, an
adapter written before its contract test tends to leak its engine's shape into the core —
which is the failure mode [ADR-0012](adr/0012-adapter-contract.md) exists to prevent.

---

## 15. Open items — resolved during the build

Recorded because each cost time to discover and none is documented upstream.

1. **`pyscn`'s output.** It does not write JSON to stdout. `pyscn analyze --json --no-open
   --select complexity,deadcode,cbo,lcom <file>` writes a timestamped report to
   `.pyscn/reports/` **relative to the working directory**. The adapter therefore runs it
   in a throwaway directory and reads the report back, which also stops it littering the
   caller's tree. Its `cbo` section defaults to `show_zeros: false`, so an uncoupled class
   is absent from the per-class list while still counted in the summary — the summary is
   the reliable read.
2. **`complexipy`'s API.** `code_complexity(source)` takes a string directly and returns a
   `CodeComplexity` with `.complexity` and `.functions`, each function carrying `.name` and
   `.complexity`. No temporary file needed.
3. **Embedding weights.** `jina-code-embeddings-0.5b` could not be licence-verified, so the
   substitute named in [ADR-0009](adr/0009-three-embedding-models.md) was taken:
   `jinaai/jina-embeddings-v2-base-code` (Apache-2.0). The three configured models are
   therefore all permissively licensed.
4. **`bandit`'s JSON.** Stable enough to pin against. `metrics._totals` carries
   `SEVERITY.*` and `CONFIDENCE.*` counts as independent axes; both are emitted rather than
   collapsed into one score. bandit exits 1 when it finds something, so only empty stdout
   is treated as failure.
5. **`pyscn`'s distribution.** Installed from PyPI as a wrapper that vendors the Go binary.
   It is invoked by absolute path, never imported.

### Discovered during the build, not anticipated by this spec

6. **Binary discovery must look beside the interpreter.** When the package is installed in
   a virtual environment, `pip install vulture` puts the console script in that
   environment's `bin/`, which is on `PATH` only while the environment is activated.
   `shutil.which` alone therefore reports engines as missing that are installed in the same
   environment. `execution.which` checks `Path(sys.executable).parent` first.
7. **`lizard`'s Halstead is per-function, and this is load-bearing.** It returns nothing for
   a fragment with no function definitions. On a corpus that is 85 % flat scripts, that is
   not a detail: it is why lizard cannot be substituted for radon, and it is now pinned by
   `test_lizard_is_not_a_substitute_for_radon_on_flat_scripts`.
8. **`pandas` embeds its full licence text in package metadata**, bundled third-party
   notices included, so a naive copyleft scan of all metadata produces false positives. The
   licence check reads licence classifiers and `License-Expression` first, and falls back
   to only the first line of the free-text field. Separately, `MPL` is a substring of
   `IMPLEMENTATION`, which appears in every package's classifiers — markers must be matched
   on word boundaries.
9. **Deeply nested literals hit CPython's parser limit before they hit a recursive walk's
   stack limit.** A fixture cannot demonstrate `RecursionError` in a depth function by
   nesting alone. The iterative implementation is still required, and
   `test_depth_is_independent_of_the_recursion_limit` demonstrates it honestly by lowering
   `sys.setrecursionlimit`.

---

## 16. Build outcome

| | |
|---|---|
| Version | 0.1.0 |
| Engines integrated | 8 (7 default, 1 optional) |
| Schema columns | 114 metric columns plus 4 identity columns |
| Catalogue entries | 108, generated from the adapters |
| Tests | 155 passing, 1 skipped |
| Lint | clean |

Every adapter is verified against its own engine's command line interface — an independent
code path — over hundreds of real files drawn from installed open-source packages. The
suite has already caught two things: `vulture`'s output depends on any path component that
looks like a test, and `lizard`'s CSV column order is not what it appears. Cyclomatic
complexity shows no divergence at all, which matters as much as the rest: a package
reporting everything as broken would be as useless as one reporting nothing as broken.
