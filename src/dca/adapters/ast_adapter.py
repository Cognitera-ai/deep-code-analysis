"""Structural metrics from the standard library ``ast`` module.

This is the **only** adapter that computes rather than delegates, and it is a deliberate,
bounded exception to ADR-0001. The justification is that no public tool emits these as
named metrics: tree-sitter, libcst, ast-grep and ast-comments all hand back a tree and
stop; pyscn emits nodes and edges of the *control-flow* graph, which is a different object.
The closest thing to prior art is each research group's private helper script.

Because there is no upstream to defer to, every definition here is documented inline and
kept simple enough to audit by reading. Roughly forty lines of counting, no cleverness.

One rule is not negotiable: **depth is computed iteratively**. The recursive version raises
``RecursionError`` on valid deeply-nested generated code, and one such fragment once
aborted an entire export (ADR-0013).
"""

from __future__ import annotations

import ast

from ..contract import Adapter
from ..parsing import parse
from ..schema import AdapterResult, Granularity, MetricSpec, NullSemantics

_INVALID = NullSemantics.INVALID_INPUT

_SPECS = [
    MetricSpec(
        key='ast_depth',
        granularity=Granularity.FILE,
        unit='levels',
        dtype='int',
        description='Deepest nesting level of the syntax tree, counted iteratively.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='total_nodes',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Every node in the syntax tree. Denominator for the ratio metrics.',
        valid_range=(1, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='functiondef_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Function definitions, async included.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='classdef_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Class definitions.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='return_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Return statements.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='call_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Call expressions.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='assign_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Assignment statements, augmented and annotated included.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='comprehension_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='List, set, dict and generator comprehensions.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='try_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Try statements.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='decorator_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description='Decorators applied to functions and classes.',
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='loop_ratio',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description=(
            'Share of nodes that are loops. A zero here is semantic: the fragment genuinely has no '
            'loops.'
        ),
        valid_range=(0, 1),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='if_ratio',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description='Share of nodes that are conditionals.',
        valid_range=(0, 1),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='import_ratio',
        granularity=Granularity.FILE,
        unit='ratio',
        dtype='float',
        description=(
            'Share of nodes that are imports. Correlates inversely with size by construction.'
        ),
        valid_range=(0, 1),
        null_semantics=_INVALID,
    ),
    MetricSpec(
        key='operational_node_count',
        granularity=Granularity.FILE,
        unit='count',
        dtype='int',
        description=(
            "Nodes doing computational work: calls, assignments, subscripts, attribute access, "
            "conditional expressions, loops, conditionals, returns and comprehensions. Exists to "
            "distinguish 'no operators' from 'radon sees no operators'."
        ),
        valid_range=(0, None),
        null_semantics=_INVALID,
    ),
]

#: Nodes that represent computational work regardless of whether radon calls them
#: operators. This is the counter that showed 99.7 % of radon's Halstead zeros sit on
#: fragments with real operator content (median 4 of these nodes), which is what separates
#: an instrument artefact from an empty program.
_OPERATIONAL = (
    ast.Call, ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Subscript, ast.Attribute,
    ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.If, ast.Return, ast.comprehension,
)

_LOOPS = (ast.For, ast.While, ast.AsyncFor)
_IMPORTS = (ast.Import, ast.ImportFrom)
_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
_ASSIGNS = (ast.Assign, ast.AugAssign, ast.AnnAssign)


def _depth(tree: ast.AST) -> int:
    """Maximum nesting depth, iteratively.

    The recursive formulation is shorter and raises ``RecursionError`` on generated code
    that nests deeply but legally. That is not hypothetical: one such fragment aborted a
    whole export before this was rewritten.
    """
    max_depth = 0
    stack: list[tuple[ast.AST, int]] = [(tree, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > max_depth:
            max_depth = depth
        stack.extend((child, depth + 1) for child in ast.iter_child_nodes(node))
    return max_depth


class AstAdapter(Adapter):
    name = "ast"
    path = "import"

    @property
    def version(self) -> str | None:
        """The interpreter's version: ``ast`` ships with Python, and its grammar is what
        decides which fragments count as valid at all."""
        import sys

        return ".".join(str(p) for p in sys.version_info[:3])

    def is_available(self) -> bool:
        return True

    @property
    def declared_metrics(self) -> list[MetricSpec]:
        return list(_SPECS)

    def analyse(self, code: str) -> AdapterResult:
        tree = parse(code)
        if tree is None:
            return self._null_result()
        try:
            return AdapterResult(values=self._measure(tree))
        except Exception as exc:  # noqa: BLE001 - R-19
            return self._degraded(fragment_id="", exc=exc)

    def _measure(self, tree: ast.AST) -> dict[str, float | int | bool | None]:
        nodes = list(ast.walk(tree))
        total = len(nodes)

        def count(types) -> int:
            return sum(isinstance(n, types) for n in nodes)

        loops = count(_LOOPS)
        ifs = count(ast.If)
        imports = count(_IMPORTS)

        def ratio(n: int) -> float:
            return round(n / total, 6) if total else 0.0

        return {
            "ast_depth": _depth(tree),
            "total_nodes": total,
            "functiondef_count": count(_FUNCS),
            "classdef_count": count(ast.ClassDef),
            "return_count": count(ast.Return),
            "call_count": count(ast.Call),
            "assign_count": count(_ASSIGNS),
            "comprehension_count": count(_COMPREHENSIONS),
            "try_count": count(ast.Try),
            "decorator_count": sum(
                len(n.decorator_list)
                for n in nodes
                if isinstance(n, (*_FUNCS, ast.ClassDef))
            ),
            "loop_ratio": ratio(loops),
            "if_ratio": ratio(ifs),
            "import_ratio": ratio(imports),
            "operational_node_count": count(_OPERATIONAL),
        }
