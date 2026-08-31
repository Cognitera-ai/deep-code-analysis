# ADR-0017 — Private until the package is ready

- **Status:** **Superseded by [ADR-0018](0018-public-repository.md)** (2026-08-31)
- **Date:** 2026-08-31
- **Supersedes:** [ADR-0014](0014-public-repository-from-day-one.md)

> The repository was opened. This record is kept because its argument — that publishing a
> repository publishes a claim about other people's tools, and that the claim has to be
> defensible — is the reason the parity suite and
> [`THIRD-PARTY-NOTICES.md`](../../THIRD-PARTY-NOTICES.md) exist.

## Context

[ADR-0014](0014-public-repository-from-day-one.md) argued for opening the repository
immediately, on the grounds that JOSS's screening gates require at least six months of
public history and that the clock starts at publication rather than at completion. That
analysis is unchanged and still correct.

The decision it produced was wrong for this project, for a reason the ADR did not weigh:
**what a public repository publishes is not only code, it is a claim.** This package's
central assertion is that widely used tools disagree with each other by an order of
magnitude and that one of them returns a saturated constant on most realistic input. That
is a claim about other people's work. Publishing it half-built — with adapters that might
still be distorting their engines, and a conformance suite that has only ever run against
one corpus — risks making that claim wrongly and in public, against named projects.

The asymmetry is stark. A delayed release costs calendar time. A public, incorrect
accusation of instrument failure costs the credibility the package exists to have.

## Decision

**The repository stays private until the package is complete enough to defend its own
claims.** "Complete enough" means, at minimum:

1. The conformance suite runs against all three corpus tiers, not just `minimal` — the
   `humaneval` tier in particular, because it is the corpus the literature uses and the one
   a reader will check the divergence figures against.
2. The divergence findings are classified as *specification difference* or *bug*
   ([ADR-0010](0010-conformance-characterises-not-certifies.md)), rather than merely
   measured. "radon and lizard differ by 9x" is an observation; "radon counts five node
   types as operators and here is the consequence" is a finding.
3. The upstream reports in `motivation.md` §7 have been filed, so the affected projects
   hear it from an issue before they hear it from a paper.

## Consequences

- **The JOSS route is deferred, not lost.** Its six-month clock starts whenever the
  repository is opened, so that route becomes available six months after that date.
- **The other routes are unaffected.** MSR's Data and Tool Showcase, ICSME's Tool
  Demonstration and SCP's Original Software Publication have no public-history gate. Any of
  them can be targeted without waiting.
- **The development history is still being built correctly.** Commits are accumulating over
  time against a specification written first, which is exactly the shape of history the
  screening gates want to see. Privacy delays when that history becomes visible; it does not
  damage it.
- **One risk is accepted knowingly:** a competitor could ship an equivalent aggregator in
  the interval. `pyscn` is moving fast in adjacent territory and could add Halstead and a
  maintainability index in one release cycle. That risk is real, and it is the price of not
  publishing a claim before it can be defended — which
  [`motivation.md`](../motivation.md) §4 already argues is the wrong thing to compete on
  anyway. The contribution that matters is the divergence characterisation, and that is
  strengthened by more measurement, not by earlier publication.

## Note for whoever opens it

Flipping visibility is a one-line operation and an outward-facing one. It belongs to the
author, not to an agent:

```bash
gh repo edit Cognitera-ai/deep-code-analysis --visibility public
```

On that day, re-read [ADR-0014](0014-public-repository-from-day-one.md): its operational
requirements — a real `LICENSE` file from the first commit, tagged releases, public issues,
an explicit AI-usage disclosure, and evidence of collaborative effort — all still apply, and
the last of them is the one that needs planning rather than a command.
