# ADR-0016 — English throughout

- **Status:** Accepted
- **Date:** 2026-08-31
- **Supersedes:** an earlier decision that kept design documents in Spanish

## Context

The author works in Spanish. An earlier version of this decision therefore split the
repository: design documents (ADRs, motivation, specification) in Spanish, and only the
published artifact — API, docstrings, README — in English.

That split was rejected on reflection. It creates three concrete problems:

1. **Artifact review reads everything.** ICSE, FSE and MSR artifact evaluation examine
   design documents, not just the API. A reviewer who cannot read the ADRs cannot evaluate
   the decisions they record — and the ADRs are where this project's actual reasoning lives.
2. **The ADRs are the contribution.** The divergence findings, the licensing analysis, the
   reversal on OO metrics: this material is meant to be read by other researchers, not just
   by the author. Locking it in Spanish halves its audience for no gain.
3. **A bilingual repository drifts.** Two languages mean two versions of the truth, and the
   translated one always falls behind.

## Decision

**Everything in this repository is in English**: code, identifiers, docstrings, comments,
log and error messages, README, ADRs, specification, motivation, tool inventory, and
generated documentation.

No exceptions. If a document is worth keeping in the repository, it is worth being readable
by the audience the package targets.

## Consequences

- Design documents originally drafted in Spanish were rewritten, not translated
  mechanically.
- The author works in Spanish: **conversation and working notes stay in Spanish**, but
  nothing that lands in this repository does.
- Column names are English, which is what every engine this package delegates to already
  uses.
