# ADR-0001 — Delegate to existing engines; do not reimplement metrics

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The project's original idea was to write our own implementations of Halstead, McCabe, the
Maintainability Index and lizard's per-function metrics, "improving" on the originals. The
appeal was total control over the definitions.

Three facts argue against it:

1. **Construct validity.** Asked "how do I know your Halstead volume is computed
   correctly?", the answer "it is not mine, it is radon 6.0.1, with the version stamped in
   the provenance envelope" is strong. The answer "trust my tests" is weak, and in an
   academic artifact that difference decides a defence.
2. **The definitions are inherently ambiguous.** Are `==` and `!=` one operator or two? Are
   docstrings comments? Every engine has already made those calls. A fresh implementation
   makes different ones, and the numbers stop being comparable with the literature being
   cited.
3. **Maintenance cost.** Reimplementing means inheriting responsibility for every future
   correction in every engine.

## Decision

**No metric is reimplemented.** Each one comes from its reference engine. The package
contributes exactly this and nothing more: a unified schema, provenance, aggregation,
robust execution, and characterisation of divergence.

The single permitted exception is the **structural AST metrics** (depth, node counts by
type, loop/conditional/import ratios), because it was verified that **no public tool emits
them as named metrics**. They are computed on the stdlib `ast` module, are roughly forty
lines, and their definition is transparent and auditable at a glance.

## Consequences

- The surface of first-party code stays small — the primary mitigation against the
  abandonment risk described in `motivation.md` §6.
- The package inherits its engines' bugs. **This is desirable:** documenting them is the
  contribution (see [ADR-0010](0010-conformance-characterises-not-certifies.md)).
- Every dependency must be pinned to an exact version, because the numbers depend on it.

## Alternatives rejected

- **Reimplement everything.** Rejected for the three reasons above.
- **Reimplement Halstead only**, to correct radon's blindness (`motivation.md` §2.2).
  Tempting, but it would produce a **fourth opinion** with no authority. The correct answer
  is to emit radon and lizard side by side ([ADR-0004](0004-no-canonical-engine.md)).
