# Changelog

Notable changes, newest first. This project follows [semantic versioning](https://semver.org),
and the **schema version is tracked separately** from the package version: consumers pin
against the schema, so adding a column is a minor schema bump and renaming or removing one
is a major bump.

## 0.1.0 — 2026-08-31

First release. Schema version 1.0.0.

### What it does

Measures a fragment of Python with nine engines and emits **138 metric columns** in one
schema, each column naming the engine that produced it, with a provenance envelope on every
run.

**Engines.** Imported: `radon`, `lizard` (≥1.24), `complexipy`, stdlib `ast`. Subprocess:
`pyscn`, `vulture`, `bandit`. Optional subprocess, both GPL and therefore never imported:
`pylint`, `prospector`.

**Metrics.** Size, cyclomatic complexity, Halstead, maintainability index, cognitive
complexity, AST depth and node structure, coupling (CBO), cohesion (LCOM4), inheritance
depth / number of children / response-for-class (DIT, NOC, RFC), control-flow structure,
dead code by two independent methods, security smells, aggregated linter findings, code
embeddings behind an extra, and metrics across git history.

### Design decisions worth knowing

- **No canonical engine.** Where several engines compute one metric, all are emitted plus
  their ratio and a divergence flag. Zero-versus-nonzero is flagged with no ratio, because
  one engine reporting absent while another reports present is stronger than a ratio can
  express.
- **No naked numbers.** Every value carries its engine; every run carries versions read
  from the running process, interpreter, and environment.
- **Nothing reimplemented.** Every metric comes from its reference engine. The single
  exception is the AST structural and CK inheritance metrics, which no public Python tool
  emits.
- **Null is never zero**, and an unavailable engine yields null columns rather than an
  error.

### Verification

171 tests. Every adapter is checked against its engine's own command line interface — a
separate code path — over hundreds of real files from installed packages. That suite found
two undocumented behaviours during development: `vulture` whitelists names when any path
component looks like a test, and `lizard`'s CSV column order is NLOC-then-CCN.

### Known limitations

- Python only. Multi-language is deliberate later work.
- DIT, NOC and RFC are intra-fragment: a base class in another module is not visible, and
  `base_classes_external` reports how often that happened.
- Two of the three conformance corpus tiers are specified but unbuilt.
- Divergences are measured but not yet classified as specification difference or bug.
