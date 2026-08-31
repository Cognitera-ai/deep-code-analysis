# ADR-0005 — Drop `multimetric`

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

`multimetric` (2.4.4, Zlib, active) was the most likely candidate to already do what this
package intends: it emits Halstead, CC, MI, COCOMO and fan-out in a single JSON, and it is
multi-language. If it covered 80 % of the vector, the smart move was to contribute to it
rather than build.

It was installed, executed, and its source read. The result disqualifies its use.

## Decision

**It is not used, neither as a dependency nor as a conformance oracle.**

### Reasons, in order of severity

1. **Its cyclomatic complexity is not McCabe.**
   `multimetric/cls/metric/cyclomatic.py` computes `max(conditions − exitpoints + 2, 0)`,
   with `conditions = {if, else, elif, case, default, for, while, and, or, &&, ||}` and
   `exitPoints = {return, exit, assert, break, continue, yield}`.
   It counts `else` as a decision point (McCabe does not) and **subtracts `return`
   statements**: adding an early exit *reduces* the reported complexity.
   Verified on a function with 4 `if` and 5 `return`:

   | Engine | CC |
   |---|---|
   | radon | 5 |
   | lizard | 5 |
   | ast-metrics | 5 |
   | **multimetric** | **1** |

2. **Its Maintainability Index is unbounded.** It uses
   `171 − 5.2·ln(V) − 0.23·CC − 16.2·ln(LOC)` with only `max(0, res)`. Verified values of
   **107.63** and **130.48**. Its own docstring claims the result is clamped to [0, 100];
   **the code does not clamp it.**

3. **It has no library API.** `__all__ = ["cls"]`; there is only `__main__.py` and `cls/`.
   `__main__.run(args)` exists, but `parse_args(*args)` splits the string into individual
   characters, which breaks any reasonable programmatic use.

4. **File-level only.** No per-function granularity, which is this package's unit of
   analysis.

5. **It never touches the AST.** It uses a pygments lexer, so it cannot contribute any
   structural metric.

## Consequences

- We lose COCOMO and the raw operator/operand breakdown. Acceptable: COCOMO is a
  project-effort estimate, not a fragment-level metric, and radon already exposes
  `h1, h2, N1, N2`.
- **Reasons 1 and 2 are publishable findings in their own right** and are recorded in
  `motivation.md` §2.4. Rejecting the tool produced evidence; it was not wasted work.
- If multimetric is ever compared against, it will be as an **object of study** in the
  divergence characterisation, never as an oracle.
