# Contributing

This project exists because the Python code-measurement ecosystem is fragmented and mostly
maintained by one or two unpaid people per tool. It is not trying to replace any of them —
it depends on all of them. What it can do is be the place where the shared problems get
worked on, so no single maintainer has to carry them alone.

If you are here because you maintain one of the engines this package wraps: **thank you**,
and please open an issue if anything here misrepresents your tool. Getting that right
matters more than anything else on this list.

## Getting set up

```bash
git clone https://github.com/Cognitera-ai/deep-code-analysis
cd deep-code-analysis

uv sync --dev                                   # or: pip install -e ".[dev]"
uv tool install pyscn vulture bandit            # the subprocess engines

uv run dca doctor                               # confirms what is reachable
uv run pytest tests/ -q                         # ~90 seconds
uv run ruff check src tests
```

`dca doctor` is the first thing to run when anything looks wrong. With nine engines, "why
is this column empty?" is the most common question, and it answers it in one line.

## The shape of the thing

```
src/dca/
  schema.py       Column naming, metric specs, what a null means
  contract.py     The Adapter base class — the one boundary every engine sits behind
  core.py         Composition: builds the schema, computes divergence between engines
  adapters/       One file per engine. They never import each other.
  execution.py    Bounded subprocess execution
  provenance.py   The envelope stamped on every run
  history.py      Measurement across git revisions
  frame.py        Output tables and writers
```

The rule that makes everything else work: **adapters return bare metric keys, the core
names the columns**. An adapter cannot claim a column belonging to another engine, and
divergence can only be computed in one place. If you find yourself wanting to import one
adapter from another, the thing you want belongs in the core.

## Adding an engine

This is the most valuable contribution and it is deliberately one file.

```python
from ..contract import Adapter
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics


class MyToolAdapter(Adapter):
    name = "mytool"
    path = "import"          # or "subprocess"

    def is_available(self) -> bool:
        ...                  # must never raise

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        ...                  # every key you promise to emit, with a description

    def analyse(self, code: str) -> AdapterResult:
        ...                  # must never raise; return a typed failure instead
```

Register it in `adapters/__init__.py` and you are done. The schema, the generated metric
catalogue, the divergence columns and the contract tests all pick it up automatically.

**If your metric shares a key with one another engine already emits, the comparison appears
for free** — and that is the interesting part, not an accident to avoid.

Four things the contract tests will hold you to:

1. `analyse()` never raises. Not on empty input, not on invalid Python, not on null bytes.
   One pathological fragment must not abort a batch of thousands.
2. Invalid Python yields nulls, never zeros. Zero is a measurement; null is an absence, and
   conflating them falsifies every statistic downstream.
3. Every declared metric has a real description ending in a full stop. It goes into
   user-facing documentation, so an undescribed metric is one nobody can use.
4. You emit only keys you declared. Anything else is silently dropped, loudly.

### If the engine is copyleft

It goes behind a **subprocess** boundary and an optional extra, never an import. This is
not a preference — `tests/test_licence.py` and a CI job enforce it, because a GPL
dependency in the import tree would make the whole package copyleft and prevent its use
inside other academic artifacts. `pylint` and `prospector` are the worked examples.

## Testing

Tests run against **real engine output, never mocks**. Mocking an engine would hide exactly
the class of bug this project exists to find: that engines disagree with each other, and
that one of them returns a saturated constant on a fifth of ordinary code.

The parity suite is the one to know about. It drives each engine's own command line
interface — a genuinely separate code path from the Python API the adapters use — over
hundreds of real files from installed packages:

```bash
uv run pytest tests/conformance/test_engine_parity.py -q       # fast, 120 files
DCA_PARITY_SAMPLE=600 uv run pytest tests/conformance/ -q      # the deep sweep
```

It has already found two things nobody had documented: `vulture` whitelists names when
*any* path component looks like a test, and `lizard`'s CSV column order is NLOC-then-CCN
rather than the reverse. Both were invisible until two independent paths were compared.

What it can establish and what it cannot: it shows the adapters reproduce their engines. It
**cannot** show a metric is correct, because there is no oracle — radon and lizard disagree
by an order of magnitude, so agreeing with both is impossible and agreeing with one is not
correctness. Please keep assertions on the right side of that line.

## Decisions

Every design decision is written down in [`docs/adr/`](docs/adr/), including the ones that
were later **reversed** and why. If you disagree with one, the reasoning is there to argue
against rather than reverse-engineer. Reversing a decision is normal — open an issue, and
if it holds up, write the ADR that supersedes it.

Start with [`docs/tech-spec.md`](docs/tech-spec.md) §4, which lists the twenty-four rulings
that were made in advance so the rest of the code did not have to keep asking.

## Good first issues

Labelled `good-first-issue` in the tracker. The three that would help most right now:

- **File the upstream reports.** Three findings belong in three other projects' trackers
  before they belong in a paper. Small, and immediately useful to people outside this repo.
- **Classify the divergences.** We measure that engines differ; labelling each difference
  as a *specification difference* or a *bug* is what turns an observation into a finding.
- **Build the HumanEval corpus tier.** Specified in the tech spec, unbuilt. Makes the
  divergence figures comparable with published literature.

## Conduct

Be accurate and be kind, in that order, and never at each other's expense. This project
makes public claims about other people's software; it holds itself to measured, versioned,
reproducible statements, and it expects the same in its issues and reviews. "radon 6.0.1
recognises five AST node types as operators" is a contribution. "radon is broken" is not.

## A note on commit identity

Commits here are authored as `29237451+TheTechSensei@users.noreply.github.com`. That is
GitHub's noreply address: it links commits to the right account without publishing a
personal email address in a repository that anyone can clone. Legal attribution lives where
it belongs — in `LICENSE` and `pyproject.toml`, under the author's full name.

Every commit also carries a `Co-Authored-By` trailer for the AI assistance used to write it.
That is not decoration: JOSS and several artifact tracks now require an explicit AI usage
disclosure, and a commit history that already records it is the honest and effortless way
to satisfy that.
