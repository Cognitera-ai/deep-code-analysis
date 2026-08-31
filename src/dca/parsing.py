"""Fragment identity and validity.

A fragment is a string of Python source, not a file and not a repository. It arrives from
an LLM response, so it may be a flat script, a bare function, or not Python at all.

There is deliberately no language detection: if it does not parse with ``ast.parse`` it is
invalid input, not "another language" (ADR-0002). A v1 that guesses languages would have
to carry a conditional schema for a capability it does not have.
"""

from __future__ import annotations

import ast
import hashlib
import re

#: Markdown fences, so a raw model response can be handed in directly.
_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)\n(.*?)```", re.DOTALL)

_PY_LANGS = {"python", "python3", "py", ""}


def sha256(code: str) -> str:
    """Fingerprint of the exact analysed text. Identical fragments share it."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def is_valid_python(code: str) -> bool:
    """Whether ``code`` parses. The gate for every static metric in the package."""
    if not code or not code.strip():
        return False
    try:
        ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return True


def parse(code: str) -> ast.AST | None:
    """Parsed tree, or None when the fragment is not valid Python."""
    try:
        return ast.parse(code)
    except (SyntaxError, ValueError):
        return None


def extract_code_blocks(raw: str) -> list[tuple[str, str]]:
    """Every fenced block in ``raw`` as ``(language, code)``.

    An unfenced response is treated as a single Python block, which is what models produce
    when the prompt asked for code and they complied without decoration.
    """
    blocks: list[tuple[str, str]] = []
    for match in _FENCE_RE.finditer(raw or ""):
        language = (match.group(1) or "python").lower()
        code = match.group(2).strip()
        if code:
            blocks.append((language, code))
    if not blocks and (raw or "").strip():
        blocks.append(("python", raw.strip()))
    return blocks


def python_blocks(raw: str) -> list[str]:
    """Just the Python fragments of a model response, in order."""
    return [code for lang, code in extract_code_blocks(raw) if lang in _PY_LANGS]
