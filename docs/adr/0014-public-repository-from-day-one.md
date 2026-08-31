# ADR-0014 — Public repository from day one

- **Status:** **Superseded by [ADR-0017](0017-private-until-ready.md)** (2026-08-31)
- **Date:** 2026-08-31

> This record is kept because its reasoning about JOSS's screening gates is still correct
> and still governs the timing. What changed is the decision, not the analysis: the
> repository stays private until the package is ready. See
> [ADR-0017](0017-private-until-ready.md).

## Context

The natural instinct was to develop privately and publish on completion, once the package
was presentable.

**That sequence closes the JOSS door irreversibly.** Its review criteria include pre-review
screening gates that produce **desk rejection**:

- A repository made public days before submission, or a commit history concentrated in a
  short window, must be flagged to the editor immediately, who may close the review.
- Required timeline: sustained development, **preferably months or years**. Explicitly **not
  acceptable**: most commits in the weeks before submission.
- For recently public repositories: **at least six months of public history**.

The clock **starts when the repository is made public**, not when the code is finished.

## Decision

**The repository is opened today, with the specification and no code.**

Opening it costs nothing and commits to nothing. Not opening it today closes the JOSS route
until six months after whenever it is eventually opened.

Operating consequences from day one:

1. Commits **spread over time**, not one dump. Specification first, code later, is a
   legitimate and verifiable development history.
2. **Tagged releases** as soon as anything is executable.
3. **Public issues**, including our own: they are the evidence of open development that
   review asks for.
4. A real `LICENSE` file from the first commit. JOSS declares the phrase "MIT license" in a
   README, without the file, **not acceptable**.

## Consequences

- The design and its mistakes are visible. That is the cost, and it is consistent with a
  project whose central contribution is documenting what others did not.
- Other routes (MSR Data and Tool Showcase, ICSME Tool Demo, SCP Original Software
  Publication) have **no** history gates, so this decision is not mandatory for them — but
  it costs nothing and preserves the option.
- **JOSS requirement to remember:** it requires an explicit *AI usage disclosure*. Given how
  this package is built, that section must be detailed and honest.
- **MSR/ICSME requirement:** a DOI in a persistent repository (Zenodo, figshare, Software
  Heritage) on publication. GitHub alone is not archival.

## Note on collaborative effort

JOSS declares **not acceptable** a single author with no evidence of community
participation, external use, or collaborative contribution. It is accepted if the paper
documents community use, or if the co-author list (advisors, collaborators) evidences a
collaborative context. **This must be planned now**, not discovered at submission: the
upstream contributions in `motivation.md` §7 and the pending OO metrics of
[ADR-0006](0006-oo-metrics-via-pyscn.md) are deliberate hooks for outside participation.
