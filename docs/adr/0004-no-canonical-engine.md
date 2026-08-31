# ADR-0004 — No canonical engine: emit radon and lizard side by side

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

`radon` and `lizard` diverge on Halstead volume by a **median factor of 14×**, with a tail
into the thousands, measured over 1500 files of installed open-source Python
(`motivation.md` §2.1). This is not noise: `radon.visitors.HalsteadVisitor` recognises only
five node types as operators.

A package presenting itself as a "unified source" has to do something about that. The
obvious options are the three bad ones:

1. **Pick a canonical engine and hide the other.** Conceals the problem and makes the
   package complicit in the bias.
2. **Average them.** Produces a number that is meaningless under either definition.
3. **Implement a third, "correct" version.** Produces a fourth opinion with no authority
   (see [ADR-0001](0001-delegate-do-not-reimplement.md)).

## Decision

**The package does not choose.** For every metric that more than one engine computes, it
emits:

- one column per engine, with the engine named in the column
  (`halstead_volume__radon`, `halstead_volume__lizard`);
- an explicit divergence column (`halstead_volume__delta_ratio`);
- a boolean flag when the divergence exceeds the threshold documented in the catalogue
  (`halstead_volume__divergent`).

No column is ever named `halstead_volume` on its own. **The bare name is forbidden in the
schema.**

## Consequences

- The schema is wider. That is the price, and it is acceptable.
- **The consumer is forced to choose consciously**, which is exactly the goal. It is no
  longer possible to read "the" Halstead without knowing whose it is.
- Backward reproducibility is untouched: whoever measured with radon still has their radon
  column, bit for bit.
- The divergence columns are the direct input to the conformance suite
  ([ADR-0010](0010-conformance-characterises-not-certifies.md)) and to the publishable
  finding.

## Non-obvious consequence

This decision turns the problem into the product. Divergence stops being a defect to manage
and becomes **the measurement the package contributes and nobody else makes**.
