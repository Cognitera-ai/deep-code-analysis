# ADR-0019 — Coloured output everywhere, an interactive TUI for one question only

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

With nine engines and 138 columns, reading a result by eye is genuinely hard, and the
package's central observation — that engines disagree — is inherently visual. `radon: 0`
beside `lizard: 139.0` in contrasting colour communicates in a second what a CSV column
never communicates at all.

The obvious response is "add a TUI", and the obvious response is half right. A terminal
interface is a real cost: it is UI code, it needs its own tests, it breaks on terminal
quirks, and it is the part of a codebase most likely to rot. For a package whose entire
argument is measurement rigour, spending maintenance budget on presentation is a trade
worth making deliberately rather than by enthusiasm.

The deciding question is what people actually do with this tool. The primary workflow is
*measure a corpus → write a Parquet → analyse it in pandas*. A TUI does nothing for that;
a file does everything.

But there is one exception, and it is the one that matters. **Exploring divergence is
genuinely exploratory.** "Where do the engines disagree most, and what does that fragment
look like?" is a question you follow rather than answer once, and following it in a CSV
means grepping, sorting, and losing your place.

## Decision

**Coloured output for every command; an interactive TUI for divergence exploration only.**

1. `rich` renders `doctor`, the analysis overview and the divergence summary.
2. `textual` powers exactly one screen, `dca explore`: fragments on the left, their engine
   disagreements on the right, filtered to disagreements by default.
3. **`rich` is a direct dependency; only `textual` sits behind the `tui` extra.** This was
   going to be the other way round until it turned out `complexipy` already imports `rich`,
   so it is present in every install regardless. Declaring it explicitly rather than
   relying on that is the point: an undeclared transitive dependency is a break waiting for
   the package that provides it to drop it. A full TUI framework is a different matter and
   stays optional.
4. **Every command still works without either.** No `rich` means plain text carrying the
   same information — never an ImportError, never a missing fact. The fallback costs
   almost nothing and is tested, so it stays even though the dependency is now direct.

Two supporting rules:

- **Colour carries meaning or it is not used.** Divergence severity is coloured; the
  absent-versus-present case gets its own colour because no ratio can express it. Nothing
  else is coloured, because if every row is emphasised no row is.
- **Null and zero render differently** (`—` and `0`). They mean different things in this
  schema, and a table that shows both as an empty cell erases the distinction the whole
  package is built around.

## Consequences

- The default `analyse` output changed from dumping the frame to a readable overview.
  Printing 138 columns to a terminal produced something nobody could read and no tool
  could consume; the full data belongs in a file, which is what `--out` is for.
- The TUI is tested headlessly through Textual's pilot, like any other code, rather than by
  someone looking at it.
- The scope is a standing commitment: `dca explore` answers one question. Requests to make
  it a general interface over the package should be weighed against this record, not
  granted by default.

## Alternatives rejected

- **A full TUI over every capability.** Serves a workflow that is better served by files,
  and multiplies the maintenance surface for no research value.
- **Putting `rich` behind the extra.** The original plan, abandoned on discovering it was
  already installed transitively — an extra that gates something always present is
  theatre.
- **No TUI at all.** Defensible, and it was the starting position. Divergence exploration
  is the one workflow that genuinely justifies the cost.
