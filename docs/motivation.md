# Motivation

Why this package exists, what gap it fills, and the evidence behind the claim.

> This document is the draft of the *statement of need* and the *state of the field*
> section that the publication routes will require. Everything it asserts is verifiable:
> first-party figures come from [`evidence/`](evidence/); external ones carry their source.

---

## 1. The problem we set out to solve first (which turned out not to be the important one)

The starting point was a practical annoyance. Measuring Python code comprehensively today
means installing between four and eight tools, learning four different output formats, and
hand-writing the glue that joins them into one table. Every research group studying
LLM-generated code rewrites that same glue from scratch.

That the fragmentation is real is documented: measuring LLM code with `radon` and `lizard`
is already routine practice in the literature, but **always as an ad hoc script, never as a
reusable tool**.

| Work | Tools used | Scale |
|---|---|---|
| arXiv:2509.12649 | Radon (CC, MI, LOC, LLOC, SLOC, Halstead volume) + Shapiro-Wilk + Mann-Whitney U | HumanEval |
| arXiv:2508.21634 | lizard + tiktoken (NLOC, CCN, unique tokens per function) | 285,249 Python samples |
| Licorish et al., *Comparing Human and LLM Generated Code* | Pylint, Radon, Bandit | 72 tasks |
| arXiv:2506.12014 (*code_transformed*) | Halstead (volume/effort), CC, MI | Multi-language |
| arXiv:2603.03823 (SWE-CI) | MI + Pylint, win/loss against human oracle | 20 LLMs |
| HumanEval + TOPSIS study | Radon, Complexipy, Bandit, Pylint | 164 problems |

Unifying that into one `import` is useful. **But it is a weak contribution**: anyone can
wrap `radon` in a DataFrame over a weekend, and there are active projects — `pyscn`, created
in August 2025 with over a thousand stars in a year — moving fast into the same territory.
If tabular unification were the only contribution, the honest recommendation would be to
build nothing.

What changed the assessment was measuring.

---

## 2. What appeared on measuring: the engines do not agree, and not by a little

Everything in this section is measured on **installed open-source Python** — pandas, numpy
and whatever else is in the environment. Nobody chose those files to make a point, and
anyone can reproduce the numbers on their own machine:

```bash
python docs/evidence/measure_radon_blindness.py
```

Output in [`evidence/radon-blindness-public-corpus.txt`](evidence/radon-blindness-public-corpus.txt).

### 2.1 radon and lizard differ by a median factor of 14

Over 1500 real files, with radon 6.0.1 and lizard 1.24.0:

| lizard/radon ratio, Halstead volume | Value |
|---|---|
| Comparable files (both > 0) | 1155 |
| Minimum | 0.15× |
| 25th percentile | 7.47× |
| **Median** | **14.17×** |
| 75th percentile | 32.38× |
| **Maximum** | **5419×** |

**Two widely used MIT tools, over ordinary production Python, differ by more than an order
of magnitude on the same named metric.**

### 2.2 The cause is in radon's source, and it is an undocumented design decision

`radon/visitors.py::HalsteadVisitor` implements exactly five visitors: `visit_BinOp`,
`visit_UnaryOp`, `visit_BoolOp`, `visit_AugAssign` and `visit_Compare`.

Nothing else. For radon, **these are not operators**: assignment (`=`), function calls,
attribute access, subscripting, the conditional expression (`IfExp`), and every control-flow
keyword.

A function that computes without arithmetic:

```python
def sum_of_multiples(limit, divisors):
    multiples = set()
    for divisor in divisors:
        multiples.update(range(divisor, limit, divisor))
    return sum(multiples)
```

| Engine | Halstead volume |
|---|---|
| radon 6.0.1 | **0** |
| lizard 1.24.0 | **139.0** |

The block contains `set()`, `range()`, `.update()`, `sum()`, a `for` loop and four
assignments. radon sees none of them as an operator.

**The bias is not random: it is systematic in the shape of the code.** It penalises code
that calls, assigns and iterates rather than calculates — which is most code.

### 2.3 The Maintainability Index saturates

When Halstead volume comes out as 0, `radon/metrics.py::mi_compute` short-circuits:

```python
if any(metric <= 0 for metric in (halstead_volume, sloc)):
    return 100.0                                        # path 1: short-circuit
...
return min(max(0.0, nn_mi * 100 / 171.0), 100.0)        # path 2: upper clamp
```

Two distinct paths to the ceiling, both returning the maximum. Measured over the same 1500
files:

| Measurement | Value |
|---|---|
| `halstead_volume == 0` | **19.8 %** |
| `maintainability_index == 100.0` exactly | **20.2 %** |

One file in five is reported as maximally maintainable because an unrelated metric could
not be computed. Nothing in radon's output distinguishes that from a genuinely pristine
file.

### 2.4 The zeros are not real

For the files where radon reports volume 0, count the operational AST nodes actually
present (`Call`, `Assign`, `Subscript`, `Attribute`, `IfExp`, `For`, `While`, `If`,
`Return`, comprehensions):

| Measurement | Value |
|---|---|
| Median operational nodes in the "empty" files | **14** |
| Files genuinely free of operational nodes | **6.7 %** |

> **Roughly 93 % of the zeros are instrument blindness, not an absence of operators.**

The effect is worse on shorter, less arithmetic code, which means it is worst precisely
where code-generation research is looking.

### 2.5 And lizard is not the fix

The obvious response — "use lizard instead" — does not work, and finding that out matters
as much as the defect. **lizard computes Halstead only inside functions.** A flat script
yields nothing at all. Switching engines trades radon's zeros for lizard's nulls.

**Neither engine measures this well, in different ways.** That is not an argument for a
third implementation ([ADR-0001](adr/0001-delegate-do-not-reimplement.md)); it is an
argument for reporting both and their disagreement
([ADR-0004](adr/0004-no-canonical-engine.md)).

### 2.6 It is not only radon

| Finding | Tool | Detail |
|---|---|---|
| CC is not McCabe | multimetric 2.4.4 | `max(conditions − exitpoints + 2, 0)`. Counts `else` as a decision and **subtracts `return` statements**: a function with 4 `if` and 5 `return` yields **1**, where radon, lizard and ast-metrics yield **5** |
| MI is unbounded | multimetric 2.4.4 | Scale 0–171 with only `max(0, res)`. Verified: MI = 107.63 and 130.48. Its own docstring claims clamping to [0,100]; the code does not |
| MI uses LLOC, not SLOC | radon 6.0.1 | `mi_parameters` returns `raw.lloc`; `mi_compute` receives it in a parameter named `sloc`. A silent divergence from the original Visual Studio formulation |
| Counter leak | lizard 1.24.0 `-ENS` | The nested-structure counter accumulates across functions **and across files**, and the value **changes with the order of files** on the command line |
| Path-sensitive output | vulture 2.16 | `Test*` classes are whitelisted if **any path component** looks like a test, so the same source reports different dead code depending on where it sits |
| Divergence in "modern" metrics too | complexipy 7.0.1 vs pyscn 1.30.0 | Cognitive complexity of the same method: **15 vs 16** |

### 2.7 What is *not* broken — measured, so the claim stays calibrated

Over the same corpus, radon's cyclomatic complexity was compared against lizard's, and
against each engine's own CLI, in `tests/conformance/test_engine_parity.py`. They agree.

**Cyclomatic complexity is solid.** So are the size metrics from `radon.raw`, whose own
invariant (`sloc + blank + multi + single_comments == loc`) is checkable.

This matters for the credibility of the whole argument: the divergence problem is specific
to Halstead and everything derived from it, not general to static analysis. A package
claiming everything is broken would be as useless as one claiming nothing is.

### 2.8 The literature announced this, without figures for Python

The canonical study is **Lincke, Lundberg & Löwe, "Comparing software metrics tools"
(ISSTA 2008)**. Nilsson, Antinyan & Gren (arXiv:1909.09682) summarise it: there are
considerable variations between the output of different tools for the same metric on the
same source code, because a metric's implementation varies from tool to tool. The concrete
ambiguities they identify: whether fan-out should count unique calls or all calls; the
`switch`/`case` problem for CC; the commented-versus-uncommented line problem for LOC.

The same work documents that **SonarQube offers 59 metrics of which 0 are empirically
validated**, against **Understand with 102 metrics of which 6 are validated**.

Nobody has published the equivalent for today's Python ecosystem, with an executable corpus.

---

## 3. Why "a single source of truth" was the wrong goal

The project's original intent was to be *the source of truth* for Python code measurement.
**That goal is incoherent as stated.**

No consensus operational definition of Halstead or of the Maintainability Index exists for
Python. The differences in §2 are not numerical noise: they are undocumented design choices
— what counts as an operator? is it normalised to 100? LOC, SLOC or LLOC? — plus at least
one reproducible bug. If `radon` and `lizard` differ by 6×, a third party that averages or
picks **does not create truth: it produces a fourth opinion**.

What *is* coherent, and where the project repositions:

> A **declared and verifiable** source of truth: a schema that emits, alongside every
> number, which engine and which version produced it, and a suite that **characterises the
> divergences instead of hiding them** under an average.

It is a downward revision of the rhetoric and an upward revision of what can actually be
defended.

---

## 4. The two contributions, ordered by difficulty to replicate

### 4.1 Characterisation of engine divergence, with an executable conformance corpus

*The hardest for a competitor to close.* A versioned corpus that pins down where and why
radon, lizard, complexipy, pyscn and ast-metrics diverge, classifying each divergence as a
**specification difference** or a **bug**.

It is hard to replicate because the value is not in the code but in the empirical work and
in reading the implementations. The findings in §2 appear in no existing publication.
**This is the project's most publishable contribution.**

An important methodological corollary: **an honest conformance suite cannot assert "this
implementation is correct", because there is no oracle.** It can only assert "reproduces
radon 6.0.1 within ε over corpus C, and diverges from lizard 1.24.0 in cases X, Y, Z for
documented reasons R". That is exactly what nobody has published.

### 4.2 Provenance envelope

*Medium difficulty.* A schema binding every measured value to the version of every engine,
the interpreter version, the hardware, and — when the code came from a model — the
generator's sampling parameters.

Verified across the whole inventory: **no tool does this.** `pyscn` emits `version` and
`generated_at`, the domain maximum; `ast-metrics` emits no provenance field; neither do
`radon`, `lizard`, `multimetric`, `wily` or `complexipy`.

The schema itself is trivial to copy. What is hard is the discipline of **never emitting a
naked number**. And the relevance is direct: without provenance, no study of code
variability is reproducible — as §2.3 shows, not even its authors would know what fraction
of their dependent variable was a saturated constant.

---

## 5. What this package deliberately does NOT claim

- **It does not claim to measure better.** It delegates to the existing engines and
  reimplements no metric ([ADR-0001](adr/0001-delegate-do-not-reimplement.md)).
- **It does not claim to resolve the divergences.** It exposes them
  ([ADR-0004](adr/0004-no-canonical-engine.md)).
- **It does not claim the metrics are valid.** The Maintainability Index in particular
  carries serious criticism: its coefficients come from a 1990s study over a small corpus of
  C and Pascal, and its validity for Python was never established. Halstead's measures carry
  similar objections going back decades. This package **measures them and documents their
  pathologies**; it does not endorse them.
- **It does not claim to be a product.** It is a research artifact, maintained as long as
  the research uses it.

---

## 6. Structural risk, stated out loud

The domain's pattern is discouraging and worth writing down from day one:

| Tool | Last release | Status |
|---|---|---|
| radon | 2023-03-26 | Stalled (>29 months). Single maintainer |
| wily | 2023-10-11 | Stalled |
| metrix++ | 2024-03-24 | Stalled |
| cognitive_complexity (Melevir) | 2022-08-09 | Stalled |
| flake8-cognitive-complexity | 2020-08-01 | Abandoned |
| SourceMeter / OpenStaticAnalyzer | copyright 2014–2016 | Abandoned |

Post-mortems were searched for all of them and **none was found**. What is observable is the
pattern: single-maintainer, unfunded projects with an active lifespan of roughly 5–7 years.
Attributing it to maintainer burnout is inference, not documented fact — but the pattern is a
direct risk to this proposal, not local colour.

Two concrete mitigations are in the design: delegating rather than reimplementing keeps the
first-party surface small ([ADR-0001](adr/0001-delegate-do-not-reimplement.md)), and isolating
each engine behind an adapter contract allows a stalled one to be replaced without touching
the rest ([ADR-0012](adr/0012-adapter-contract.md)).

---

## 7. Pending upstream contributions

Findings from §2 that deserve reporting to their projects, independently of this package.
High value, low cost, and they should be filed before any of this appears in a paper:

1. **`rubik/radon`** — the maintainability index saturating at exactly 100.0 for about a
   fifth of ordinary open-source Python, with the cause (the five `HalsteadVisitor`
   visitors) and the consequence for anyone using MI as a response variable.
2. **`terryyin/lizard`** — the `-ENS` extension's counter leaking across functions and
   across files, with a dependency on invocation order.
3. **`terryyin/lizard`** — its PyPI classifier reads `Freeware` while its `LICENSE.txt` is
   full MIT. A metadata inconsistency worth a one-line fix.
4. **`jendrikseipp/vulture`** — the path-component whitelisting is correct behaviour but is
   not documented; a note would save the next person the afternoon it cost here.
