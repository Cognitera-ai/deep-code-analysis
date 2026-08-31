# ADR-0015 — Metric documentation is generated from code, not written

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

A package with ~150 columns needs a catalogue saying what each one is, which engine
produces it, in what unit and over what range. Hand-written, that catalogue drifts out of
sync within weeks, and a catalogue that lies is worse than none.

The pattern that works is generating the document from the code's own definitions and
having CI regenerate it on every push, so the two cannot drift apart unnoticed.

## Decision

**The metric catalogue is generated from the adapters**, which declare their keys,
granularity, unit and description as part of the contract
([ADR-0012](0012-adapter-contract.md)).

- The generated document carries a "do not edit by hand" header.
- CI regenerates it and **fails if the result differs from what is committed**. An
  out-of-date catalogue is a build failure, not a pending task.
- The same source feeds the human-readable catalogue, schema validation and parity tests.

## Consequences

- The catalogue cannot lie.
- **It contains only environment-independent facts.** Engine versions are deliberately
  excluded: they differ per machine, so including them made the document regenerate
  differently on every interpreter and the drift check fail for a reason that had nothing
  to do with the schema. Versions belong in the per-run provenance envelope
  ([ADR-0007](0007-provenance-is-mandatory.md)), where they are a measurement rather than
  a constant.
- Adding a metric without describing it becomes an error rather than an oversight.
- It is also exactly what artifact review guidelines look for: complete, verifiable API
  documentation.

## Precedent

A pattern proven in production, with CI enforcing it, before being adopted here.
