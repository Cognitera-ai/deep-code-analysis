# ADR-0010 — The conformance suite characterises divergence; it does not certify correctness

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The original intent was a suite that would "put the existing tools up against mine" to
demonstrate that the package was well built.

That formulation presupposes an oracle, and **there is none**. Validating against radon and
validating against lizard are mutually incompatible goals: they differ by a median factor of
6× on the same metric over the same corpus. No consensus operational definition of Halstead
or of the MI exists for Python against which "correct" could be measured.

## Decision

**The suite does not assert correctness. It asserts reproduction and characterises
divergence.**

A valid assertion from the suite has this shape:

> "Reproduces radon 6.0.1 within ε over corpus C, and diverges from lizard 1.24.0 in cases
> X, Y, Z for documented reasons R."

An invalid assertion, forbidden in this project:

> "The Halstead volume computed by this package is correct."

### Structure

1. **Reproduction tests.** For each delegated engine, that the package returns exactly what
   the engine returns, over a versioned corpus. This proves the adapter does not distort.
2. **Divergence matrix.** For each metric computed by more than one engine, the distribution
   of ratios between engines over the corpus, with its extreme cases named.
3. **Classification.** Each divergence is labelled either a **specification difference** (a
   different, documented design decision) or a **bug** (behaviour the engine itself would
   not defend). lizard's `-ENS` leak is the second kind; radon's Halstead blindness is the
   first.
4. **Versioned golden files**, regenerable with one command, whose diff is the signal that
   an engine changed behaviour.

## Consequences

- **It is the project's most publishable contribution** and its hardest part to replicate:
  the value is not in the code but in the empirical work and in having read the
  implementations.
- It makes the corpus a first-class, versioned, citable artifact rather than a test folder.
- It forces exact version pins on every engine: with ranges the suite stops being
  deterministic.
- It is the early-warning mechanism against the abandonment risk: when a stalled engine
  finally ships, the golden files say exactly what changed.
