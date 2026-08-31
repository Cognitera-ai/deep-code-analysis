# ADR-0009 — Three embedding models, behind an optional extra

- **Status:** Accepted
- **Date:** 2026-08-31

## Context

`microsoft/unixcoder-base` (768 dims, 125 M, CPU) is the encoder most often reached for in
this space. Verifying the state of the art shows that **it is no longer state of the art**:
it appears in the 2025–2026 literature as a historical antecedent, and the current reference
point is MTEB Code / CoIR.

Concrete figure from the CodeSage model card (Code2Code Search, 9-language average):
CodeSage-v2-Base (356 M) = **47.17** beats CodeSage-Large v1 (1.3 B) = 38.51 and
OpenAI-Text-3-Large = 28.65.

At the same time, for measuring *structural variability between samples of the same
problem*, a small encoder pre-trained on ASTs and data-flow graphs is defensible on cost,
determinism and reproducibility — and it is what has already been run over thousands of
samples.

## Decision

**Three models, all optional behind the `embeddings` extra:**

| Model | Licence | Dims / size | Why |
|---|---|---|---|
| `microsoft/unixcoder-base` | Apache-2.0 | 768 / 125 M | AST- and dataflow-pretrained; cheap and deterministic |
| `codesage/codesage-base-v2` | Apache-2.0 | 1024 / 356 M | Open state of the art with a good size/quality ratio |
| `jina-code-embeddings-0.5b` | verify | 0.5 B | A different family, so the comparison is not inbred |

`voyage-code-3` is excluded despite its quality: it is a proprietary API and therefore
**not reproducible**, which makes it inadmissible under
[ADR-0007](0007-provenance-is-mandatory.md).

## Consequences

- `torch` and `transformers` are **never** hard dependencies. With them the package goes
  from a few megabytes to more than a gigabyte and nobody installs it.
- Having three lets any choice **be justified by comparison** rather than assumed. That is
  the argument that survives review.
- Provenance must stamp model identifier, weights revision and device: the same model on
  GPU and on CPU can produce vectors that differ in the last decimals.
- **Scope warning:** JOSS declares pre-trained models out of scope. The package's
  contribution **is not** the embeddings part, and the paper must not present it as such.

## Open item

Verify the exact licence of the `jina-code-embeddings-0.5b` weights before fixing it as a
default. If it is not permissive, the substitute is `jina-embeddings-v2-base-code`
(Apache-2.0) or a `Qwen3-Embedding` (Apache-2.0).
