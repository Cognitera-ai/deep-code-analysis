# ADR-0011 — `pylint` out of the import tree; optional subprocess extra

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

`pylint` (GPLv2+) has the broadest smell catalogue in Python, and its score appears as a
comparison variable in the LLM-code literature (SWE-CI, Licorish et al.). But importing it
would force the package to be copyleft
([ADR-0003](0003-mit-licence-and-copyleft-exclusion.md)).

Accepting the GPL was weighed, since the project is research-only with no commercial
interest. Reviewing the actual contribution showed it was unnecessary: pylint is a
**findings** tool, not a **measurement** tool, and its contribution to a metric vector was
always marginal. `pyscn`, `vulture` and `bandit` — all permissive — cover dead code,
coupling and security better.

There is a further problem, independent of licensing: representing pylint's catalogue as one
column per message code produces a schema of hundreds of columns that breaks on every minor
pylint release, because its codes change.

## Decision

**`pylint` does not enter the import tree.** It remains available as an **optional
subprocess extra** (`pip install deep-code-analysis[pylint]`), which preserves the
package's MIT licence.

When the extra is active, the package emits the **global score and counts grouped by
category** (convention / refactor / warning / error), **never one column per message code**.
Category grouping is stable across versions; individual codes are not.

## Consequences

- The package keeps MIT without giving up comparability with the literature that uses the
  pylint score.
- Smell granularity is knowingly sacrificed. `bandit` and `vulture` cover the two families
  that matter most for generated code.
- **Rule for the building agent:** the pylint adapter is low priority. If the build budget
  runs out, it is dropped with no consequence for the rest.
