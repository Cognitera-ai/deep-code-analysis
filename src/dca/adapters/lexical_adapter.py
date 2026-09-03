"""The program's vocabulary: how many different words it is made of.

This is the second adapter that computes rather than delegates, and it exists for a
specific reason: it is the honest answer to the problem the rest of this package spends its
time documenting.

radon's Halstead measures a program's vocabulary — but only counts five AST node types as
operators, so on code that calls, assigns and iterates rather than calculates it reports
zero, for about one file in five of ordinary Python and far more of generated code. The
quantities Halstead was reaching for are real and useful. They just need to be counted over
*every* token instead of an arbitrary subset.

So this adapter counts them the obvious way, with Python's own ``tokenize``: every
identifier, keyword, operator and literal is a word. It cannot report zero on a non-empty
program, which is the whole point.

No public Python tool emits these as named metrics, which is what admits them under the
same exception as the AST structural metrics (ADR-0001).

Two levels:

* **Token level** — vocabulary size, length and their ratio. These are Halstead's η and N
  without his operator table.
* **AST level** — the same vocabulary broken down by what kind of name it is: variables the
  author bound, functions they defined, things they called, attributes they reached for,
  modules they imported. A name can appear in more than one, deliberately: ``count`` may be
  both a variable and an attribute, and collapsing that would lose the distinction.
"""

from __future__ import annotations

import ast
import io
import keyword
import tokenize

from ..contract import Adapter
from ..parsing import is_valid_python
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

_INVALID = NullSemantics.INVALID_INPUT

#: Tokens that are layout or prose rather than vocabulary.
#:
#: Indentation and newlines are excluded because counting them would make formatting style
#: a lexical property, which it is not. **Comments are excluded for a different and more
#: debatable reason:** they are words the author wrote, but they are not words the *program*
#: is made of, and Halstead's vocabulary — which these metrics reconstruct honestly — counts
#: operators and operands, not prose. Including them would also let a docstring-heavy file
#: outscore a dense one on lexical diversity, which measures the writing rather than the code.
#:
#: Docstrings are *not* excluded, because they are STRING tokens indistinguishable from any
#: other literal at this level. That asymmetry is a known wart, and is why comment density
#: is reported separately by radon rather than folded in here.
_LAYOUT = frozenset(
    {
        tokenize.ENCODING,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
        tokenize.COMMENT,
    }
)

_SPECS = [
    MetricSpec(
        key="distinct_tokens",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Different words the program is made of, counting every identifier, keyword, "
            "operator and literal. Halstead's vocabulary without his operator table."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="lexical_tokens",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Total words in the program, layout excluded. Halstead's length, counted over "
            "every token rather than an arithmetic-only subset."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="type_token_ratio",
        granularity=Granularity.FILE,
        unit="ratio",
        dtype="float",
        description=(
            "Distinct words over total words: lexical diversity. Falls with length by "
            "construction, so compare it only between programs of similar size."
        ),
        valid_range=(0, 1),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_identifiers",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Different names the author chose, keywords excluded. The program's own "
            "vocabulary rather than the language's, and never zero on a non-empty program."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_variables",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Different names bound by assignment, loop, comprehension or parameter."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_functions_defined",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description="Different function names the program defines.",
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_calls",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description=(
            "Different things the program calls, taking the last segment of a dotted "
            "call, so `s.count(...)` counts as `count`."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_attributes",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description="Different attributes the program accesses.",
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key="distinct_imports",
        granularity=Granularity.FILE,
        unit="count",
        dtype="int",
        description="Different modules and names the program imports.",
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
]


class LexicalAdapter(Adapter):
    name = "lexical"
    path = "import"

    @property
    def version(self) -> str | None:
        """The interpreter's version: `tokenize` and `ast` ship with Python, and its
        grammar decides what counts as a token at all."""
        import sys

        return ".".join(str(p) for p in sys.version_info[:3])

    def is_available(self) -> bool:
        return True

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        return list(_SPECS)

    def analyse(self, code: str) -> AdapterResult:
        if not is_valid_python(code):
            return self._null_result()
        try:
            return AdapterResult(values=self._measure(code))
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

    def _measure(self, code: str) -> dict[str, float | int | bool | None]:
        try:
            tokens = [
                t
                for t in tokenize.generate_tokens(io.StringIO(code).readline)
                if t.type not in _LAYOUT
            ]
        except (tokenize.TokenError, IndentationError):
            # A fragment can parse and still fail to tokenise cleanly at the very end.
            return dict.fromkeys(spec.key for spec in _SPECS)

        tree = ast.parse(code)
        words = [t.string for t in tokens]
        identifiers = {
            t.string
            for t in tokens
            if t.type == tokenize.NAME and not keyword.iskeyword(t.string)
        }

        variables: set[str] = set()
        functions: set[str] = set()
        calls: set[str] = set()
        attributes: set[str] = set()
        imports: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                variables.add(node.id)
            elif isinstance(node, ast.arg):
                variables.add(node.arg)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.add(node.name)
            elif isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    calls.add(func.id)
                elif isinstance(func, ast.Attribute):
                    calls.add(func.attr)
            elif isinstance(node, ast.Attribute):
                attributes.add(node.attr)
            elif isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.update(alias.name for alias in node.names)
                if node.module:
                    imports.add(node.module)

        return {
            "distinct_tokens": len(set(words)),
            "lexical_tokens": len(words),
            "type_token_ratio": round(len(set(words)) / len(words), 6) if words else None,
            "distinct_identifiers": len(identifiers),
            "distinct_variables": len(variables),
            "distinct_functions_defined": len(functions),
            "distinct_calls": len(calls),
            "distinct_attributes": len(attributes),
            "distinct_imports": len(imports),
        }
