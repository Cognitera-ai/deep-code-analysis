<div align="center">

# deep-code-analysis

**Every Python code metric the community knows how to compute, in one table —
with the provenance to reproduce it and the disagreements left visible.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![Engines: 9](https://img.shields.io/badge/engines-9-brightgreen.svg)](#the-engines)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](tests/)

</div>

---

## Start with a problem

Here is a function. What is its Halstead volume?

```python
def sum_of_multiples(limit, divisors):
    multiples = set()
    for divisor in divisors:
        multiples.update(range(divisor, limit, divisor))
    return sum(multiples)
```

Two widely used, MIT-licensed, actively cited tools answer:

| Engine | Halstead volume |
|---|---|
| `radon` 6.0.1 | **0** |
| `lizard` 1.24.0 | **139.0** |

Not a rounding difference. One says the function has no measurable content at all.

Measured over **1500 files of installed open-source Python** — pandas, numpy, whatever is
in your environment — they differ by a **median factor of 14×**, with a tail into the
thousands. And because `radon`'s maintainability index short-circuits to exactly `100.0`
whenever Halstead volume is zero, **one file in five scores a perfect maintainability
rating** for a reason that has nothing to do with maintainability.

Of those zero-volume files, **93 % contain real operators** — a median of 14 calls,
assignments and branches that radon does not count. The zeros are the instrument, not the
code.

Papers are published on these numbers. None of them report which engine produced them.

Reproduce all of it yourself: `python docs/evidence/measure_radon_blindness.py`

```python
from dca import analyse

result = analyse(source)
result.value("halstead_volume", "radon")           # 0.0
result.value("halstead_volume", "lizard")          # 139.0
result.metrics["halstead_volume__divergent"]       # True
result.provenance.analysis_chain                   # {'radon': '6.0.1', 'lizard': '1.24.0', ...}
```

That is the whole idea. **No column is called `halstead_volume`.** Every column names the
engine that produced it, because pretending there is one answer is how the disagreement
stayed invisible.

---

## What it does

One call, nine engines, one schema — **138 metric columns**, each tagged with its source.

```python
from dca import analyse_many

frame = analyse_many(fragments)

frame.metrics()              # one row per fragment, 114 columns
frame.divergence_summary()   # where engines disagreed, and by how much
frame.null_rates()           # what could not be measured, and by whom
frame.to_parquet("out/")     # metrics · functions · degradations · provenance
```

| What you get | Why it is separate |
|---|---|
| **`metrics`** | One row per fragment. The main table. |
| **`functions`** | Per-function detail — aggregating to mean/max/min is lossy, so the detail survives. |
| **`degradations`** | Every engine failure, logged. A broken engine must not look like a metric that does not apply. |
| **`provenance`** | Engine versions, interpreter, environment, and optionally the sampling parameters that generated the code. |

### Measured

Size · cyclomatic complexity · Halstead · maintainability index · cognitive complexity ·
AST depth and node structure · coupling (CBO) · cohesion (LCOM4) · **inheritance depth, number
of children and response-for-class (DIT / NOC / RFC)** · CFG structure · dead code (two
independent methods) · security smells · aggregated linter findings · code embeddings ·
**metrics across git history**.

---

## Install

```bash
pip install deep-code-analysis
```

The three subprocess engines are installed separately — they run as programs, not imports,
which is what keeps this package's licence clean:

```bash
pip install pyscn vulture bandit
dca doctor          # what is reachable, at what version
```

<details>
<summary>Optional extras</summary>

```bash
pip install "deep-code-analysis[embeddings]"   # 3 code encoders (pulls torch)
pip install "deep-code-analysis[pylint]"       # pylint score, subprocess only (GPL)
```
</details>

### Command line

```bash
dca analyse src/ --out results/ --format parquet --summary
dca history . --trend lloc__radon        # how the project grew, revision by revision
dca catalogue                            # every column: engine, unit, range, meaning
dca doctor                               # why is this column empty?
```

---

## Three things nothing else does

**1. It never hides a disagreement.** Where several engines compute the same metric, all of
them are emitted, plus their ratio and a divergence flag. Zero-versus-nonzero is flagged
with *no* ratio, because "absent" versus "present" is stronger than any number can express.

**2. It never emits a naked number.** Every value carries its engine. Every run carries an
envelope: engine versions read from the running process, interpreter, hardware, and — for
generated code — model, temperature, top-p, seed. No other tool in this space does this,
which is precisely why nobody noticed a dependent variable was a constant.

**3. It proves it did not distort anything.** Every adapter is checked against its engine's
own command line interface — a separate code path — over hundreds of real files. Wrapping
nine tools is easy; wrapping them without quietly changing their answers is the part that
needs evidence.

**4. It has a time axis.** Every other capability answers "what is this code like?". This
one answers "what has it been becoming?", which is usually the more useful question — a
complexity of 12 says little, a complexity that went from 4 to 12 says a lot.

```python
from dca import measure_history, trend

frame = measure_history(".", limit=200, every=5)
trend(frame, "cyclomatic_complexity_mean__radon", how="mean")
```

Files are read from git rather than the working tree, so an uncommitted edit cannot
contaminate a historical point, and a file that did not exist at a revision produces no row
rather than a zero — otherwise a project growing reads as a metric collapsing.

---

## The engines

This package **reimplements nothing**. Every number comes from a tool that has been getting
it right for years:

| | Engine | Licence | Contributes |
|---|---|---|---|
| import | [radon](https://github.com/rubik/radon) | MIT | size · McCabe · Halstead · maintainability |
| import | [lizard](https://github.com/terryyin/lizard) | MIT | per-function metrics · second Halstead reading |
| import | [complexipy](https://github.com/rohaquinlop/complexipy) | MIT | cognitive complexity |
| import | Python `ast` | PSF | structural metrics |
| subprocess | [pyscn](https://github.com/ludo-technologies/pyscn) | MIT | CBO · LCOM4 · CFG · clones |
| subprocess | [vulture](https://github.com/jendrikseipp/vulture) | MIT | dead code |
| subprocess | [bandit](https://github.com/PyCQA/bandit) | Apache-2.0 | security smells |
| optional | [pylint](https://github.com/pylint-dev/pylint) | GPL-2.0+ | score · category counts |
| optional | [prospector](https://github.com/prospector-dev/prospector) | GPL-2.0 | aggregated findings across six linters |

> **Credit belongs upstream.** These projects did the hard part. Most are maintained by one
> or two unpaid people, and several have not shipped a release in years. This package is
> not a replacement or a competitor — it is a place where the ecosystem's shared problems
> can be worked on without any single maintainer having to carry them.
>
> If this is useful in published work, **cite the engines too**.

Full licence position: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

---

## How we know we didn't break anything

Wrapping eight tools is easy. Wrapping them *without silently changing their answers* is the
part that needs proving.

Every adapter is checked against **its own engine's command line interface** — a completely
separate code path from the Python API the adapters use — over hundreds of real files drawn
from installed packages: pandas, numpy, and whatever else is in the environment. Thousands
of files nobody chose to make the test pass.

```bash
pytest tests/conformance/test_engine_parity.py           # fast: 120 files
DCA_PARITY_SAMPLE=600 pytest tests/conformance/          # deeper
```

It has already earned its place twice. It found that **`vulture`'s output depends on the
path**: `Test*` classes are whitelisted if *any* path component looks like a test, so the
same source reports different dead code depending on where it sits. And it caught a column
order I had assumed wrong in `lizard`'s CSV — invisible, because both columns are small
integers. Both are now documented and pinned rather than silently wrong.

What the suite proves, and what it cannot: it shows the adapters reproduce their engines.
It **cannot** show any metric is "correct" — there is no oracle. radon and lizard disagree,
so agreeing with both is impossible and agreeing with one is not correctness. That
distinction is load-bearing and [written down](docs/adr/0010-conformance-characterises-not-certifies.md).

---

## Contributing

**Adding an engine is one file.** Every engine sits behind a single contract, so a new
adapter needs no knowledge of any other, and the contract tests apply to it automatically
the moment it is registered:

```python
class MyAdapter(Adapter):
    name = "mytool"
    path = "import"                      # or "subprocess"

    def is_available(self) -> bool: ...
    @property
    def declared_metrics(self) -> list[MetricSpec]: ...
    def analyse(self, code: str) -> AdapterResult: ...
```

Register it in `adapters/__init__.py`. The schema, the metric catalogue, the divergence
columns and the parity tests all pick it up on their own. If your metric overlaps one
another engine already emits, **the comparison appears for free** — that is the interesting
part.

### Open problems, if you want a real one

| | Why it matters | Size |
|---|---|---|
| **Classify every divergence** | We measure that engines differ. Labelling each as *specification difference* or *bug* is the part that makes it publishable — and useful upstream. | Medium, high value |
| **File the upstream issues** | `lizard`'s `-ENS` counter leaks across files; `radon`'s MI saturates on a fifth of ordinary code; `vulture`'s path whitelisting is undocumented. All three deserve to hear it from an issue. | Small, immediately useful |
| **More engine parity** | `pyscn` and `complexipy` are compared shallowly. Deeper coverage means more confidence and probably more findings. | Medium |
| **Multi-language** | v1 is Python only, deliberately. `lizard` already handles 20+ languages; `tree-sitter` is the natural path. | Large |
| **A real corpus tier** | The conformance corpus has 12 hand-written fragments. Larger public tiers are specified but unbuilt. | Medium |

Full guide: [CONTRIBUTING.md](CONTRIBUTING.md).

Every decision in this project is written down and argued in [`docs/adr/`](docs/adr/) — 17
records, including the ones that were **reversed** and why. If you disagree with one, the
reasoning is there to argue against rather than reverse-engineer.

Start here: [`docs/tech-spec.md`](docs/tech-spec.md) · [`docs/motivation.md`](docs/motivation.md) · [`docs/tool-landscape.md`](docs/tool-landscape.md)

---

## Status

**v0.1.0 — working, tested, not yet on PyPI.**

Nine engines · 138 metric columns · 171 tests · metric catalogue generated from the code and
enforced by CI · every adapter checked against its engine's own CLI over real open-source
code.

Honest about what is missing: two of three conformance corpus tiers are unbuilt, divergences
are measured but not yet classified, and the upstream issues are unfiled. See
[ADR-0018](docs/adr/0018-public-repository.md).

## Documentation

| | |
|---|---|
| [`docs/tech-spec.md`](docs/tech-spec.md) | The build specification: rulings, adapter contract, schema, acceptance criteria |
| [`docs/motivation.md`](docs/motivation.md) | Why this exists, with the measurements |
| [`docs/tool-landscape.md`](docs/tool-landscape.md) | ~40 tools in this space, verified: licence, status, what each emits |
| [`docs/metric-catalogue.md`](docs/metric-catalogue.md) | Generated. Every column, engine, unit, range, meaning |
| [`docs/adr/`](docs/adr/) | Every decision and its reasoning |

## Citation

If this is useful in published work, please cite it **and the engines it delegates to** —
they did the measurement, this package arranged it. See
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

## Author

Yonathan Berith Jaramillo Ramírez

## Licence

MIT. Every dependency in the import tree is permissive, and
[a CI job proves it](tests/test_licence.py) on every commit.
