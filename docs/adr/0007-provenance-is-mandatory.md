# ADR-0007 — Provenance is mandatory: never a naked number

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

It was verified across the whole inventory that **no tool in the domain stamps
provenance**. `pyscn` emits `version` and `generated_at`, which is the maximum found;
`ast-metrics` emits no provenance field at all; neither do `radon`, `lizard`, `multimetric`,
`wily` or `complexipy`.

The practical consequence is measured in `motivation.md` §2.3: radon's MI saturates at
exactly 100.0 for about a fifth of ordinary open-source Python, and **studies using radon
do not report what fraction of their dependent variable was a saturated constant**, because
nothing told them. A number without provenance is neither reproducible nor auditable.

## Decision

**Every emitted value carries the identity of the engine that produced it, and every export
carries a complete provenance envelope.**

The envelope records, at minimum:

| Block | Fields |
|---|---|
| Analysis chain | Exact version of every engine used (radon, lizard, complexipy, pyscn, vulture, bandit) |
| Interpreter | `sys.version_info`, `sys.implementation.name` |
| Package | Own version and schema hash |
| Environment | OS, architecture, and hardware when embeddings are used |
| Embeddings | Model identifier, weights repository revision, device |
| Input | `sha256` of the analysed code |
| Generation *(optional)* | When the code came from a model: model, temperature, top-p, seed and other sampling parameters |

Versions are read from the **running process** (`importlib.metadata`), never from
dependency declaration files: a floor specifier (`radon>=6.0.1`) is re-resolved at install
time, and reporting it would be a fabrication.

## Consequences

- The discipline is the hard part, not the schema. **No public function may return a bare
  scalar**; every output is wrapped or accompanied.
- It is a verifiable acceptance criterion: a test walks the schema and fails if any metric
  column lacks an identifiable engine.
- The generation block is what makes the package specifically useful for LLM research, and
  it is optional so it does not burden other users.

## Precedent

This design is a pattern proven in production elsewhere before being generalised here.
