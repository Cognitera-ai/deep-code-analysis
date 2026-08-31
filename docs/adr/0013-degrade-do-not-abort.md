# ADR-0013 — Degrade to null, never abort the batch

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

This package's natural input is **LLM-generated code**: often syntactically invalid,
sometimes pathological, occasionally hostile without meaning to be. In the originating
project, three separate incidents cost entire exports:

1. A deeply nested but valid block raised `RecursionError` in the recursive AST-depth
   computation and aborted the whole export.
2. A block printing inside an infinite loop accumulated hundreds of MB per second in the
   parent process buffer until the container was OOM-killed.
3. radon's `cc_visit` and `h_visit` raise on exotic but parseable code.

An export of thousands of samples dying because of one of them is unacceptable: that is
precisely the package's use case.

## Decision

**No single fragment's failure may affect another fragment.**

| Situation | Behaviour |
|---|---|
| The code does not parse | Metrics are **null**, never zero. The row exists and is flagged invalid |
| An engine raises on a fragment | Only that engine's metrics go null; the others continue |
| An engine is not installed | Its columns are null for the whole batch; the rest is computed |
| A subprocess exceeds time or memory | It is killed, its columns go null, the batch continues |
| Captured output exceeds the cap | Drained to the end discarding the excess, with a truncation marker |

Four non-negotiable implementation rules:

1. **Null and zero are not interchangeable.** Zero is a measurement; null is an absence.
   Conflating them falsifies any downstream statistic.
2. **AST depth is computed iteratively**, never recursively.
3. **Subprocess output is read by draining to EOF with a cap**, never by buffered capture.
   And reading continues past the cap, discarding: if we stopped reading, the child would
   block on a full pipe and a program that prints a lot then exits cleanly would be
   misreported as a timeout.
4. **Every degradation is logged** with the engine, the exception type and the fragment
   identifier. A silent degradation is a defect.

## Consequences

- The package is usable over large, dirty corpora, which is its reason for existing.
- The **null rate per engine is itself a research datum**: in `motivation.md` §2.3 it is
  exactly what revealed radon's MI saturation. It must be reported, not hidden.
- A broken engine produces empty columns instead of a loud error. The degradation log is
  what stops that going unnoticed, which is why it is mandatory.

## Precedent

Each rule here comes from an incident in production analysis work, not from speculation.
