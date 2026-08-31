# Third-party notices

`deep-code-analysis` **delegates every metric to an existing engine and reimplements none**
([ADR-0001](docs/adr/0001-delegate-do-not-reimplement.md)). It depends on those engines; it
does not contain, vendor, fork or redistribute any of their code. Installing this package
installs its dependencies from PyPI in the ordinary way, each under its own licence and
from its own maintainers.

The numbers this package reports are their work. The schema, provenance and divergence
analysis around those numbers are ours.

## Licence position

This package is **MIT**. That is only sustainable because of a rule the build enforces
rather than trusts: **no copyleft dependency may enter the import tree**
([ADR-0003](docs/adr/0003-mit-licence-and-copyleft-exclusion.md)). `tests/test_licence.py`
checks it on every run and CI runs it as its own job, so a violation shows up as a failed
check rather than as a licensing surprise years later.

### Imported — must be permissive

| Package | Licence | What it provides |
|---|---|---|
| [radon](https://github.com/rubik/radon) | MIT | Raw size counts, cyclomatic complexity, Halstead, maintainability index |
| [lizard](https://github.com/terryyin/lizard) | MIT ¹ | Per-function tokens, parameters, length, CCN; a second Halstead reading |
| [complexipy](https://github.com/rohaquinlop/complexipy) | MIT | Cognitive complexity |
| [pandas](https://github.com/pandas-dev/pandas) | BSD-3-Clause | Tabular output |
| [NumPy](https://github.com/numpy/numpy) | BSD-3-Clause | Distance computation |
| [PyArrow](https://github.com/apache/arrow) | Apache-2.0 | Parquet output |
| Python `ast` | PSF | Structural metrics |

¹ lizard's PyPI classifier reads `Freeware`, which is not a licence. Its shipped
`LICENSE.txt` contains the full MIT grant, and the repository's licence is treated as
authoritative. This is a metadata inconsistency worth a one-line fix upstream, and it is
noted in [`docs/tool-landscape.md`](docs/tool-landscape.md).

### Invoked as subprocesses — never imported

These are separate programs, executed through the operating system and communicated with
over stdout. No linking occurs and no derivative work is created.

| Tool | Licence | What it provides |
|---|---|---|
| [pyscn](https://github.com/ludo-technologies/pyscn) | MIT | CBO, LCOM4, CFG structure, dead code, APTED clone detection |
| [vulture](https://github.com/jendrikseipp/vulture) | MIT | Dead code by name resolution |
| [bandit](https://github.com/PyCQA/bandit) | Apache-2.0 | Security smells |
| [pylint](https://github.com/pylint-dev/pylint) | **GPL-2.0-or-later** | Score and category counts — **optional extra** |

**pylint is the reason this distinction exists.** Its licence is why it is reached across a
process boundary and never imported
([ADR-0011](docs/adr/0011-pylint-as-subprocess-extra.md)). It is not installed unless you
ask for it (`pip install "deep-code-analysis[pylint]"`), and if you never do, no GPL code is
present at all.

If you install that extra, you are installing pylint yourself, from PyPI, under its own
licence. This package neither ships it nor relinks it.

### Optional model weights

The `embeddings` extra downloads encoders from Hugging Face at first use. They are not
redistributed here, and each is governed by its own model card:

| Model | Licence |
|---|---|
| [microsoft/unixcoder-base](https://huggingface.co/microsoft/unixcoder-base) | Apache-2.0 |
| [codesage/codesage-base-v2](https://huggingface.co/codesage/codesage-base-v2) | Apache-2.0 |
| [jinaai/jina-embeddings-v2-base-code](https://huggingface.co/jinaai/jina-embeddings-v2-base-code) | Apache-2.0 |

## Cognitive complexity

The metric originates in a SonarSource white paper. A metric definition is not itself
copyrightable and several projects implement it independently, which is why complexipy and
pyscn can both compute it. **The white paper's text is © SonarSource and is not reproduced
anywhere in this repository** — only the metric is used, through those implementations.

## On what this project says about other projects

This package reports that widely used engines disagree with one another, sometimes by an
order of magnitude. Those are claims about other people's work, made in public, so they are
held to a standard:

* **Every claim is measured, and the measurement is reproducible.** The scripts are in
  [`docs/evidence/`](docs/evidence/) and the parity suite in
  [`tests/conformance/`](tests/conformance/) runs against real code.
* **Every claim names its version.** "radon 6.0.1 recognises five AST node types as
  operators" is checkable and falsifiable; "radon is broken" is neither, and is not
  something this project says.
* **Design decisions are distinguished from defects.** radon's Halstead scope is a design
  decision with a documented consequence. lizard's `-ENS` counter leaking across files is a
  defect. These are labelled differently on purpose
  ([ADR-0010](docs/adr/0010-conformance-characterises-not-certifies.md)).
* **Findings go upstream before they go into a paper.** The affected projects should hear
  it from an issue first ([`docs/motivation.md`](docs/motivation.md) §7).

None of this is a criticism of the engines or their maintainers. They are unpaid,
long-lived, widely relied upon, and this package would not exist without them. Documenting
where they diverge is meant to make them **more** usable in research, not less trusted.

## Attribution

If this package is useful in published work, please cite the underlying engines too. They
did the measurement; this package arranged it.
