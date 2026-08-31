"""Neural code embeddings — three models, all optional.

``torch`` and ``transformers`` are **never** hard dependencies. With them the package goes
from a few megabytes to more than a gigabyte, and a metrics library that costs a gigabyte
to install does not get installed. Everything here imports lazily, so the scalar vectors
keep working when the extra is absent (ADR-0009).

Why three rather than one. UniXcoder is a 2022 model that today's literature treats as a
historical antecedent, and an open 356 M encoder from 2024 beats encoders four times its
size on code retrieval. Offering models from three different families lets a choice be
justified *by comparison* rather than by habit, which is the argument that survives review.

``voyage-code-3`` is excluded despite its quality: it is a proprietary API, so a vector it
produces cannot be reproduced from the provenance envelope, which makes it inadmissible
here (ADR-0007).

A scope note: JOSS considers pre-trained models out of scope for its reviews. The
contribution of this package is not the embeddings, and the paper must not present it as
such.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd


@dataclass(frozen=True, slots=True)
class EmbeddingModel:
    """One encoder, with the metadata provenance needs."""

    key: str
    repo: str
    dims: int
    note: str


#: The three supported encoders (ADR-0009).
MODELS: dict[str, EmbeddingModel] = {
    "unixcoder": EmbeddingModel(
        key="unixcoder",
        repo="microsoft/unixcoder-base",
        dims=768,
        note=(
            "AST- and dataflow-pretrained, 125 M. Kept for continuity with corpora already encoded "
            "with it."
        ),
    ),
    "codesage": EmbeddingModel(
        key="codesage",
        repo="codesage/codesage-base-v2",
        dims=1024,
        note="356 M, Apache-2.0. Open state of the art at a good size/quality ratio.",
    ),
    "jina": EmbeddingModel(
        key="jina",
        repo="jinaai/jina-embeddings-v2-base-code",
        dims=768,
        note="A different model family, so the comparison is not inbred. 8192-token context.",
    ),
}

DEFAULT_MODEL = "unixcoder"
MAX_TOKENS = 512
BATCH_SIZE = int(os.getenv("DCA_EMBED_BATCH", "16"))


class EmbeddingsUnavailableError(RuntimeError):
    """Raised when the ``embeddings`` extra is not installed.

    A clear error beats a null column here: unlike a missing analysis engine, a missing
    encoder is always the caller asking for something they did not install, and silently
    returning nothing would look like the model produced no output.
    """


def is_available() -> bool:
    """Whether the extra is installed. Never raises."""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=3)
def _load(repo: str):
    """Load tokenizer and model once per repo, pinned to CPU.

    CPU is deliberate: these encoders are small, the work is post-hoc, and on a machine
    that is also running inference for generation, competing for the GPU would slow the
    thing that matters. It also keeps the vectors deterministic across hosts.
    """
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:  # pragma: no cover - guarded by is_available()
        raise EmbeddingsUnavailableError(
            "embeddings need the extra: pip install 'deep-code-analysis[embeddings]'"
        ) from exc

    torch.set_num_threads(max(1, (os.cpu_count() or 2) - 1))
    tokenizer = AutoTokenizer.from_pretrained(repo)
    model = AutoModel.from_pretrained(repo)
    model.eval()
    model.to("cpu")
    return tokenizer, model


def _masked_mean(last_hidden_state, attention_mask):
    """Mean-pool token embeddings, ignoring padding.

    Padding tokens carry no information but do carry activations; averaging over them makes
    a short fragment's vector drift toward whatever the pad embedding happens to be, and
    the drift scales with how much padding there is. Masking removes a length artefact
    that would otherwise show up as a similarity signal.
    """
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def embed(texts: Sequence[str], *, model: str = DEFAULT_MODEL) -> list[list[float]]:
    """Encode fragments into fixed-width vectors on CPU."""
    if model not in MODELS:
        raise ValueError(f"unknown model {model!r}. Available: {', '.join(sorted(MODELS))}")
    if not is_available():
        raise EmbeddingsUnavailableError(
            "embeddings need the extra: pip install 'deep-code-analysis[embeddings]'"
        )
    import torch

    spec = MODELS[model]
    tokenizer, torch_model = _load(spec.repo)
    vectors: list[list[float]] = []
    with torch.no_grad():
        for start in range(0, len(texts), BATCH_SIZE):
            # An empty fragment still needs a row, so it is encoded as a single space
            # rather than dropped: the embedding matrix must stay aligned with the
            # metrics table row for row.
            batch = [t if (t and t.strip()) else " " for t in texts[start : start + BATCH_SIZE]]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            )
            output = torch_model(**encoded)
            pooled = _masked_mean(output.last_hidden_state, encoded["attention_mask"])
            vectors.extend(pooled.cpu().tolist())
    return vectors


def embedding_frame(
    fragments: dict[str, str], *, model: str = DEFAULT_MODEL
) -> pd.DataFrame:
    """The embedding matrix: one row per fragment, ``dim_0 … dim_N`` (R-14).

    Kept in its own table rather than inline: three models at 768–1024 dimensions would
    otherwise bury the ~150 scalar columns that are the package's main output.
    """
    spec = MODELS[model]
    ids = list(fragments)
    vectors = embed([fragments[i] for i in ids], model=model)

    records = []
    # strict: a model returning a different number of vectors than fragments would
    # otherwise silently truncate the matrix.
    for fragment_id, vector in zip(ids, vectors, strict=True):
        record: dict[str, object] = {"fragment_id": fragment_id, "model": spec.key}
        # Pad or truncate defensively so the schema width is stable even if a model
        # returns an unexpected size.
        for i in range(spec.dims):
            record[f"dim_{i}"] = vector[i] if i < len(vector) else 0.0
        records.append(record)
    return pd.DataFrame.from_records(records)


def provenance_block(models: Sequence[str]) -> dict[str, dict[str, object]]:
    """What the envelope records about the encoders that ran (ADR-0007).

    The device is included because the same model on CPU and GPU can differ in the last
    decimals, which is enough to make two runs non-identical and confuse anyone comparing
    them without knowing why.
    """
    block: dict[str, dict[str, object]] = {}
    for key in models:
        spec = MODELS.get(key)
        if spec is None:
            continue
        block[key] = {
            "repo": spec.repo,
            "dims": spec.dims,
            "device": "cpu",
            "max_tokens": MAX_TOKENS,
        }
    return block
