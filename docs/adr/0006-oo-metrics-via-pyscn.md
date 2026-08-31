# ADR-0006 — OO metrics delegated to `pyscn`, not implemented

- **Status:** Accepted
- **Date:** 2026-08-31
- **Reverses:** an earlier design that planned to implement them by hand

## Context

The initial design assumed that object-oriented design metrics — coupling between objects
(CBO), depth of inheritance tree (DIT), response for a class (RFC), lack of cohesion
(LCOM) — **had no tooling in Python at all**, and existed properly solved only for Java
(CK, JDepend) and C# (NDepend). On that premise an entire phase of first-party code was
planned, estimated at 4–5 working sessions — the largest block in the project.

**The premise was correct until 2025 and stopped being correct.** `pyscn`
(https://github.com/ludo-technologies/pyscn, MIT, repository created 2025-08-06, 1,039 ★ in
one year) emits **CBO per class** and **LCOM4 per class** — with `method_groups`,
`instance_variables`, `total_methods`, `excluded_methods` — plus module dependencies, CFG
nodes and edges per function, `nesting_depth`, `if`/loop/except counts, CFG-based dead code
detection, and clone detection using **APTED** (tree edit distance).

## Decision

**OO metrics come from `pyscn`, invoked as a subprocess.** None are implemented here.

`pyscn` is a Go binary with a Python wrapper that only exposes `main()`, so integration is
by subprocess and JSON consumption — consistent with
[ADR-0012](0012-adapter-contract.md), which already provides for adapters of that kind.

## Consequences

- **The largest block of first-party code is eliminated from the project.** The total
  estimate drops from ~26–36 sessions to ~20–28.
- The package additionally gains APTED clone detection and CFG-based dead code, neither of
  which was planned.
- It adds a subprocess dependency on a downloaded binary, which must be pinned to an exact
  version and verified at startup.
- `cohesion` (GPLv3) is now doubly rejected: on licensing
  ([ADR-0003](0003-mit-licence-and-copyleft-exclusion.md)) and because its metric is a
  non-canonical percentage variant, inferior to pyscn's LCOM4.

## Still uncovered

**DIT (depth of inheritance) and RFC (response for a class) are emitted by no Python tool.**
They are declared v2 roadmap — and are a natural hook for an outside contributor.

## Lesson

This decision reverses a premise that had been true for two years and stopped being true
one year ago. **The inventory in [`tool-landscape.md`](../tool-landscape.md) must be
re-verified before any submission for publication**, because the domain moves faster than
its reputation as a mature field suggests.
