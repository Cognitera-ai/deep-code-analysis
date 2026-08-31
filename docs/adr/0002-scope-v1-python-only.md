# ADR-0002 — v1 scope: Python only

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

Several engines in the set are multi-language: `lizard` supports more than twenty
languages, `multimetric` uses pygments lexers, `ast-metrics` covers PHP, Go and Python. It
would be tempting to expose that capability from the start.

But multi-language forces language detection, per-language schema variation, a much larger
CI matrix, and — above all — giving up the stdlib `ast` module, which is the basis of the
structural metrics and of the only adapter that is first-party code.

Beyond that, the use case motivating the package (variability of LLM-generated code) is
today overwhelmingly Python.

## Decision

**v1 measures Python only.** There is no language detector: if the input does not parse
with `ast.parse`, it is invalid input, not "another language".

Multi-language is declared as later work, not as an omission.

## Consequences

- The schema is fixed rather than conditional, which simplifies versioning.
- `lizard` is used only for its per-function Python metrics; its multi-language value goes
  unexploited in v1.
- The adapter architecture ([ADR-0012](0012-adapter-contract.md)) must carry a `language`
  field from day one even though it always reads `"python"`, so that adding languages does
  not break the schema.
- `tree-sitter` is recorded as the natural v2 path and is **not** installed in v1.
