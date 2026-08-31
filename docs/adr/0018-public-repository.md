# ADR-0018 — The repository is public

- **Status:** Accepted
- **Date:** 2026-08-31
- **Supersedes:** [ADR-0017](0017-private-until-ready.md)

## Context

[ADR-0017](0017-private-until-ready.md) argued for staying private until the package could
defend its own claims, on the grounds that a public repository publishes an assertion about
other people's tools, not just code.

The author opened the repository, and renamed it from `deep-ai-code-analysis` to
`deep-code-analysis`. Both are recorded here rather than argued with: the decision is the
author's, and this record exists so the repository does not carry documents that
contradict its own state.

The reasoning in 0017 was not wrong, but two things weakened it. First, the parity suite
now exists: every adapter is checked against its engine's own command line interface over
hundreds of real files, so "our numbers might be our own distortion" is a question with an
answer rather than an open risk. Second, the argument treated publication as the moment a
claim becomes public, when in practice it is publication *of a paper* that does that. A
repository is where a claim can be checked, and being checkable earlier is better.

## Decision

**The repository is public, under the name `deep-code-analysis`.** The PyPI distribution
takes the same name; the import name stays `dca`.

The obligations that come with being public are now live, not deferred:

1. **Claims about other projects are held to the standard in
   [`THIRD-PARTY-NOTICES.md`](../../THIRD-PARTY-NOTICES.md):** measured, reproducible,
   version-specific, and separating design decisions from defects.
2. **Findings go upstream before they go into a paper.** The two issues in
   [`motivation.md`](../motivation.md) §7 should be filed early rather than at
   submission time.
3. **The licence boundary is now externally visible and externally verifiable.** The
   licence CI job is no longer only for us.

## Consequences

- **The JOSS six-month clock starts now**, from the day the repository became public. That
  route reopens roughly six months later. MSR, ICSME and SCP have no such gate and remain
  available immediately ([ADR-0014](0014-public-repository-from-day-one.md), whose analysis
  of those gates still stands).
- **The development history is the right shape.** Specification first, then implementation,
  then a parity suite, committed over time — which is what the screening criteria look for
  and what a repository dumped in one commit cannot show.
- **The name change is a breaking change for nobody**, because nothing has been released
  yet. It has to happen now or never.
- **Collaborative effort is now the item that needs planning**, not the history. JOSS
  declares a single author with no external participation unacceptable. The v2 roadmap
  items — DIT and RFC, which no Python tool provides — are deliberately left open as
  contribution hooks ([ADR-0006](0006-oo-metrics-via-pyscn.md)).

## Still true from ADR-0017

Its definition of "ready" is not void; it is now a roadmap rather than a gate:

1. The conformance suite should run against all three corpus tiers, not only `minimal`.
2. Divergence findings should be classified as specification difference or bug, not merely
   measured.
3. The upstream reports should be filed.

None of those block being public. All of them block claiming the work is finished.
