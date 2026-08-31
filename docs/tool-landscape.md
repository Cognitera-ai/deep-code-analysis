# Inventory of Python code-measurement tools

State of the domain verified on **30–31 August 2026**. This document is the draft of the
*state of the field* section and of the *build vs. contribute* justification the publication
routes require.

**Status convention.** *Active* = release within the last 12 months. *Maintained* = release
within the last 24 months. *Stalled* = no release in more than 24 months. *Abandoned* = no
activity in more than 48 months.

**Reading the "used here" column:** `import` = direct dependency · `subprocess` = invoked as
a binary, never entering the import tree · `extra` = behind an optional extra · `—` = not
used · `oracle` = used only in the conformance suite to characterise divergence.

---

## a) Classic metrics: LOC, McCabe, Halstead, Maintainability

| Tool | Version / date | Licence | Status | Importable | Used here |
|---|---|---|---|---|---|
| **radon** | 6.0.1 — 2023-03-26 | MIT | **Stalled** (>29 months; push 2024-10-20; ~2,012 ★; single maintainer) | Yes | **import** |
| **lizard** | 1.24.0 — 2026-08-19 | MIT ¹ | Active | Yes | **import** |
| **multimetric** | 2.4.4 — 2026-03-06 | Zlib | Active | **No** (`__all__ = ["cls"]`) | **—** (see ADR-0005) |
| **wily** | 1.25.0 — 2023-10-11 | Apache-2.0 | **Stalled** (push 2024-07-10; ~1,229 ★) | Yes | **—** (architectural reference) |
| **mccabe** | 0.7.0 — 2022-01-24 | MIT | Release stalled; repo active (683 ★) | Yes | **—** (radon covers it) |
| **metrix++** | 1.8.1 — 2024-03-24 | MIT | **Stalled** (92 ★) | Not in practice | — |
| **xenon** | 0.9.3 — 2024-10-21 | MIT | Borderline (~22 months) | Yes | — |
| **OpenStaticAnalyzer / SourceMeter** | copyright 2014–2016 | **EUPL v1.2** | **Abandoned** | No (CLI) | **—** (copyleft, ADR-0003) |
| **SciTools Understand** | Commercial | Proprietary | Active | Own API | — |
| **SonarQube / sonar-python** | push 2026-08-28; 251 ★ | Open-core (proprietary + LGPL) | Active | No | — |
| **cloc** | — | **GPL v2** | Active | No | **—** (copyleft) |
| **scc** | — | MIT | Active | No | — |
| **tokei** | push 2026-05-06; 14,860 ★ | MIT | Maintained | No | — |
| **pygount** | 3.2.0 — 2026-04-08 | BSD | Maintained | **Yes** | — (importable alternative to cloc) |

¹ lizard's `LICENSE.txt` contains the full MIT text with no carve-outs. Its PyPI classifier
says `Freeware`: **that is a package metadata inconsistency**, not a different licence. Worth
reporting upstream.

### What each one actually emits

- **radon** — `raw`: loc, lloc, sloc, comments, multi, blank, single_comments ·
  `cc`: CC per function/method/class + rank · `hal`: h1, h2, N1, N2, vocabulary, length,
  calculated_length, volume, difficulty, effort, time, bugs · `mi`: MI 0–100 + rank.
- **lizard** — Per function: cyclomatic_complexity, nloc, token_count, long_name,
  start/end_line, full_parameters, top_nesting_level, max_nesting_depth. Per file: nloc,
  token_count, CCN, ND, averages. Extensions: `-Ehalstead`, `-ENS`, `-Ewordcount`, `-Ecpre`,
  `-Eoutside`, `-EIgnoreAssert`.
  **Note:** the `fan_in`/`fan_out` fields exist but **return 0**.
  **Known bug:** `-ENS` accumulates its counter across functions and files, and depends on
  invocation order (see `motivation.md` §2.6).
  **Known limitation:** Halstead is computed **only inside functions**, so it returns nothing
  for flat scripts — which is why it is not a drop-in replacement for radon (`motivation.md`
  §2.5).
- **multimetric** — File level only: comment_ratio, cyclomatic_complexity,
  fanout_external/internal, halstead_{volume,difficulty,effort,bugprop,timerequired}, loc,
  maintainability_index, operands/operators_{sum,uniq}, pylint, tiobe_*.
  **Its CC is not McCabe and its MI is unbounded** (see ADR-0005).

### Finding on SonarQube

The official metric documentation **includes neither Halstead nor a Maintainability Index**.
Its *Maintainability* category is the SQALE index (technical debt in minutes and a ratio), a
different construct. Furthermore, the table of CC counting rules per language covers ABAP,
C/C++, C#, COBOL, Java, JS/TS, PHP, PL/I, PL/SQL and VB.NET — **Python does not appear**.

**Consequence:** comparing radon against SonarQube on MI is impossible, not because they
differ but because SonarQube does not compute that metric. Any cross-comparison in this
project excludes SonarQube for this reason, not for licensing.

### Correction: `PyMetrics` is not what it looks like

The PyPI package `PyMetrics` (1.0.10, 2023-11-28, Apache-2.0) **is not** the classic
PyMetrics static-analysis tool. It is *"Versatile metrics collection for Python"* by
**Eventbrite, Inc.**, a statsd-style application telemetry library with no relation to source
code metrics. Reg Charney's historical PyMetrics is not on PyPI under that name.
**Removed from the competitor inventory.**

---

## b) Cognitive complexity

Defined in the SonarSource white paper. The *definition* is freely implementable — complexipy,
pyscn and Melevir all do it — but **the white paper's text is © SonarSource and must not be
reproduced**.

| Tool | Version / date | Licence | Status | Importable | Used here |
|---|---|---|---|---|---|
| **complexipy** | 7.0.1 — 2026-08-12 | MIT | **Active** (821 ★; push 2026-08-30) | **Yes, real API** | **import** |
| **pyscn** | 1.30.0 — 2026-08-26 | MIT | **Active** | No (Go binary) | **subprocess** |
| **cognitive_complexity** (Melevir) | 1.3.0 — 2022-08-09 | MIT | **Stalled** (47 ★) | Yes | **oracle** |
| **flake8-cognitive-complexity** | 0.1.0 — 2020-08-01 | MIT | **Abandoned** | Plugin | — |
| **sonar-python** | active | LGPL / proprietary | Active | No | — |

complexipy's real API: `code_complexity()`, `file_complexity()`, `FileComplexity`,
`FunctionComplexity`, `LineComplexity`, `compute_diff`, `RefactorPlan`.

**Verified divergence:** complexipy and pyscn give **15 vs. 16** on the same method. There is
no canonical reference implementation for Python.

---

## c) OO design metrics: coupling, cohesion, inheritance

> **Important correction.** Until 2025 it was reasonable to claim these metrics existed only
> for Java and C#. **`pyscn` invalidated that claim** in August 2025. This package's original
> design planned to implement them by hand; that phase was removed
> ([ADR-0006](adr/0006-oo-metrics-via-pyscn.md)).

| Tool | Version / date | Licence | Emits | Used here |
|---|---|---|---|---|
| **pyscn** | 1.30.0 — 2026-08-26; 1,039 ★; repo created 2025-08-06 | MIT | **CBO** per class, **LCOM4** per class (with `method_groups`, `instance_variables`, `total_methods`, `excluded_methods`), module dependencies, CFG-based dead code, APTED clone detection | **subprocess** |
| **cohesion** | 1.2.0 — 2024-12-09 | **GPLv3** | Cohesion as % of methods using each instance variable — **a non-canonical variant**, not LCOM1–4 | **—** (copyleft + pyscn's LCOM4 is better) |
| **Understand** | Commercial | Proprietary | DIT, RFC, CBO, LCOM, NOC | — |
| **OpenStaticAnalyzer** | Abandoned | EUPL v1.2 | Cohesion, coupling, inheritance | **—** (copyleft) |
| **pydeps** | 3.0.7 | BSD-2 | Dependency graph | — |
| **pyan3** | 2.8.1 | — | Call graph | — |
| **PyCG** | 0.0.8 | Apache | Call graph | — |

**radon, lizard, multimetric and ast-metrics emit no LCOM, DIT, RFC or CBO.** ast-metrics
emits only `coupling.efferent` at file level.

**Still uncovered in Python: DIT (depth of inheritance) and RFC (response for a class).**
Declared v2 roadmap ([ADR-0006](adr/0006-oo-metrics-via-pyscn.md)).

---

## d) Structural AST / CST

| Tool | Version / date | Licence | Emits a metric vector? | Used here |
|---|---|---|---|---|
| **`ast`** (stdlib) | — | PSF | No, but it is the basis | **import** |
| **tree-sitter** (Python binding) | 0.26.0 — 2026-06-30 | MIT | **No.** The tree only | — (v2 multi-language) |
| **libcst** | 1.9.0 — 2026-07-29 | MIT | **No.** Format-preserving CST | — |
| **ast-grep** | 0.45.3 — 2026-08-31 | MIT | **No.** Search and rewrite | — |
| **ast-comments** | 1.3.0 — 2026-02-22 | MIT | **No.** `ast` wrapper | — |
| **ast-metrics** | 0.43.0 — 2026-08-28; 153 ★ | MIT (package) | **Yes, with caveats** | **oracle** |

**ast-metrics:** the PyPI package exposes only `PINNED_VERSION` and `version`; it downloads a
42 MB Go binary on first use. JSON is **file level only**: `complexity.cyclomatic`,
`volume.{loc,lloc,cloc,halstead*}`,
`maintainability.{maintainabilityIndex, maintainabilityIndexWithoutComments, commentWeight}`,
`risk.score`, `coupling.efferent`. Formats: HTML, JSON, Markdown, OpenMetrics, SARIF.
**It emits no provenance field.**

> **Confirmed gap:** no public tool emits **AST depth** or **node counts by type** as named
> metrics. The closest is pyscn, which emits `nodes` and `edges` **of the CFG** (not the AST),
> plus `if_statements`, `loop_statements`, `exception_handlers`, `switch_cases`,
> `nesting_depth`. These metrics are first-party in this package, computed on the stdlib
> `ast` module.

---

## e) Code smells and Python antipatterns

| Tool | Version | Licence | Used here |
|---|---|---|---|
| **vulture** | 2.16 | MIT | **subprocess** (dead code) |
| **bandit** | — | Apache-2.0 | **subprocess** (security smells) |
| **pylint** | 4.0.8 | **GPLv2+** | **optional subprocess extra** (ADR-0011) |
| **ruff** | 0.16.5 | MIT | — (C901/mccabe rule; possible v2) |
| **wemake-python-styleguide** | 1.8.0 | MIT | — |
| **sourcery** | 1.45.0 | Proprietary | — |
| **Pysmell** (Chen et al., 2016) | Academic, not on PyPI | — | — |
| **DPy** (MSR 2025) | See §g | Not verified | — |

**Pysmell** (Chen et al., *Information and Software Technology*, 2018) defines 10–11
Python-specific smells: Large Class, Long Method, Long Message Chain, Long Parameter List,
Long Lambda Function, Long Scope Chaining, Long Base Class List, Long Ternary Conditional
Expression, Complex List Comprehension, Multiply Nested Container.
**Name collision:** the PyPI package `pysmell` (0.7.3, 2009) is an unrelated autocompletion
library.

**DPy** (MSR 2025, Data and Tool Showcase Track) supports eight *design smells*, eleven
*implementation smells* and several quality metrics for Python. **It is the closest
publication precedent to this project.**

---

## f) Neural code representations

| Model | Licence | Dims / size | Used here |
|---|---|---|---|
| **microsoft/unixcoder-base** | **Apache-2.0** | 768 / 125 M | **extra** (continuity with prior corpus) |
| **codesage/codesage-base-v2** | **Apache-2.0** | 1024 / 356 M | **extra** |
| **jina-code-embeddings-0.5b** | — (verify) | 0.5 B | **extra** |
| microsoft/CodeBERT (repo hosting `unixcoder.py`) | **MIT** | — | — |
| CodeT5 / CodeT5+ | BSD-3 | — | — (generative encoder-decoder) |
| codesage-large-v2 | Apache-2.0 | 2048 / 1.3 B | — |
| jina-embeddings-v2-base-code | Apache-2.0 | 8,192-token context | — |
| Qwen3-Embedding (0.6B/4B/8B) | Apache-2.0 | — | — |
| voyage-code-3 | Proprietary (API) | — | — (not reproducible) |

**Where UniXcoder stands today.** The current reference point is **MTEB Code / CoIR**, not
CodeSearchNet in isolation. UniXcoder (arXiv:2203.03850, 2022) appears in the 2025–2026
literature as a **historical antecedent**, not as state of the art. From the CodeSage model
card (Code2Code Search, 9-language average): CodeSage-v2-Base (356 M) = **47.17** beats
CodeSage-Large v1 (1.3 B) = 38.51 and OpenAI-Text-3-Large = 28.65.

**Why UniXcoder is kept anyway:** for measuring *structural variability* between samples of
the same problem, a 125 M encoder pre-trained on ASTs and data-flow graphs is defensible on
cost, determinism and reproducibility — and it is what has already been run. But it **must be
justified by comparison**, not assumed ([ADR-0009](adr/0009-three-embedding-models.md)).

---

## g) Meta-tools and aggregators

| Tool | Status | Licence | Note | Used here |
|---|---|---|---|---|
| **prospector** | 1.19.1 — 2026-07-16; 2,087 ★ | **GPL-2.0** | Aggregates pylint, pyflakes, pycodestyle, mccabe, dodgy, pydocstyle, vulture. **Aggregates findings, not numeric metrics** | **—** (copyleft) |
| **MegaLinter** | **Not on PyPI** | — | Docker/Node orchestrator for ~70 linters. Findings, not metrics | — |
| **CodeCharta** | push 2026-08-30; 501 ★ | BSD-3 | **Not on PyPI.** Java/TypeScript. Its target output is a `.cc.json` for visualisation, not an analytical table | — |
| **wily** | Stalled since 2023-10 | Apache-2.0 | **The only importable Python aggregator with a unified metric schema** | **—**, but its "operator" abstraction is the architectural reference ([ADR-0012](adr/0012-adapter-contract.md)) |

---

## Verdict: does this package already exist?

**No.** No importable Python library emits, in a single tabular schema, radon's metrics +
lizard's metrics + structural AST metrics + code embeddings. This was verified by installing
and running the six plausible candidates.

The obstacle is not that nobody tried — multimetric, ast-metrics, pyscn and wily all did — but
that **every attempt stops before crossing at least two of the four domains**, and none
crosses the fourth, because static analysis and neural code representation belong to
communities that do not overlap.

### The three closest, and exactly what they lack

| Candidate | Strength | Why it is not enough |
|---|---|---|
| **multimetric** | The most cited as a "unifier" | File level only · no API (`__all__ = ["cls"]`, and `parse_args(*args)` splits the string into characters) · no AST (pygments lexer) · no embeddings · **and its two flagship metrics are wrong** |
| **pyscn** | Structurally the richest (CBO, LCOM4, CFG, clones) | Not a Python library (a Go binary wrapper exposing only `main()`) · no Halstead · no MI · no embeddings · minimal provenance |
| **wily** | The only importable aggregator with a unified schema | Stalled since 2023-10 · wraps radon only (no per-function tokens or parameters) · no AST · no embeddings · its unit of analysis is the git revision, not the generated sample |

### The honest caveat

**The gap is smaller than it looks.** Measuring LLM code with radon and lizard is already
routine in the literature, and `pyscn` — created August 2025, over a thousand stars in a year
— is moving fast into the same territory and could add Halstead and MI in one release cycle.

That is why the contribution **does not rest on tabular unification**, the most visible gap
and the one that protects least, but on divergence characterisation, provenance, and the
distance to a human reference ([`motivation.md`](motivation.md) §4).

---

## Pending verification

Inherited from the research report, unresolved:

1. **OpenStaticAnalyzer / SourceMeter**: last release date and real status. Only the licence
   (EUPL v1.2) and Python support were verified.
2. **GitHub stars** for lizard, multimetric, tree-sitter, ast-grep, MegaLinter, cohesion
   (unauthenticated API rate limit).
3. **PyPI download counts** for any package (pypistats not consulted).
4. **Understand (SciTools)**: current Python metric list and licensing terms. Nilsson et al.
   (2019) was used, which may be out of date.
5. **Exact CodeCharta and MegaLinter output for Python.**
6. **DPy**: public repository availability and licence.
7. **SonarQube's CC counting rules for Python**: absent from the metric definitions page, and
   no documentation located.
8. **Whether radon's use of LLOC in the MI is documented anywhere** as intentional, or is a
   slip.
9. **wily releases after 1.25.0**: its `HISTORY.md` mentions a Ruff-AST-based cyclomatic
   operator that appears in no PyPI release.
10. **Exact licence of the `jina-code-embeddings-0.5b` weights** on Hugging Face.
11. **Post-mortems** for the abandoned tools: searched for and **none found**. Attributing it
    to single-maintainer burnout is inference over the pattern, not documented fact.

Every one of these must be resolved **before** the package is submitted for publication,
because they all appear in the *state of the field* section.
