# ADR-0012 — A single adapter contract

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

The package integrates seven heterogeneous engines: three are imported (`radon`, `lizard`,
`complexipy`), three are invoked as binaries (`pyscn`, `vulture`, `bandit`), one is the
stdlib (`ast`), and there are three embedding models behind an extra. Their outputs range
from Python objects to subprocess JSON, at different granularities (file, function, class).

Without a common boundary, each adapter imposes its shape on the core and the package
becomes unmaintainable — which is exactly how aggregators die.

`wily` (Apache-2.0, stalled) solved this with its "operator" abstraction, and is the best
architectural reference in the domain.

## Decision

**Every engine is integrated behind a single interface**, with an explicit contract:

| Element | Requirement |
|---|---|
| Identity | Engine name, version resolved at runtime, path (`import` / `subprocess`) |
| Availability | A method reporting whether the engine can run here and now, without raising |
| Declared metrics | The list of keys the adapter promises to emit — the catalogue is **derived from code**, never hand-written |
| Granularity | Each metric declares its level: file, function or class |
| Execution | Takes code, returns a normalised result or a typed failure |
| Failure | Never raises upward: returns a degraded result ([ADR-0013](0013-degrade-do-not-abort.md)) |

Derived rules, mandatory:

1. **No adapter writes to the schema directly.** It returns its vector; the core composes
   it. This is what lets adapters be written **in parallel and without coordination**.
2. **No adapter knows about another.** The divergence columns of
   [ADR-0004](0004-no-canonical-engine.md) are computed by the core, never by an adapter.
3. **The engine name goes in the column name**, always, without exception.
4. **A stalled or broken engine is disabled without touching the rest** — the architectural
   mitigation against the risk in `motivation.md` §6.

## Consequences

- The adapter construction phases are parallelisable, which is what makes the ~1.5-day
  schedule feasible.
- Adding a new engine means writing an adapter; it does not touch the core.
- The metric catalogue and documentation are **generated** from the adapters, so they cannot
  drift out of sync with the code
  ([ADR-0015](0015-documentation-generated-from-schema.md)).
- It adds a layer of indirection that would be over-engineering for a single-engine package.
  With seven, it is what keeps it alive.
