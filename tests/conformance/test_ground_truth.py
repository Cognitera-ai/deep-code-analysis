"""Hand-verified ground truth for every metric that *has* a ground truth.

This suite answers a question the parity suite cannot: not "does the adapter reproduce the
engine?" but "is the engine right?". It can only do that for metrics whose definition is
unambiguous — line counts, statement counts, function and class counts, McCabe's number,
tree depth. For those, a person can count by hand, and here a person did.

Every expected value below was computed by reading the fragment, with the reasoning written
next to it. The fragments mirror the shape of LLM-generated solutions to short problems:
flat scripts with a dictionary, a loop, an `if`, a print; occasionally a function. If a tool
disagrees with a value here, one of two things is true — the tool is wrong, or the hand
count is — and either is worth knowing.

What this suite deliberately does **not** do is assert a "correct" Halstead volume or
maintainability index. Those have no oracle: Halstead never defined an operator for Python,
and three tools have three answers. For them the honest test is the one in
`test_halstead_operator_tables_are_documented`: it pins *what each engine counts*, so a
reader can judge, rather than pretending one of them is right.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

import pytest

from dca.adapters.ast_adapter import AstAdapter
from dca.adapters.complexipy_adapter import ComplexipyAdapter
from dca.adapters.radon_adapter import RadonAdapter


@dataclass(frozen=True)
class Truth:
    """One fragment and everything a person can count in it."""

    name: str
    code: str
    total_lines: int
    blank_lines: int
    comment_lines: int
    lloc: int              # logical lines: one per statement, radon's definition
    functiondef_count: int
    class_count: int
    return_count: int
    call_count: int
    assign_count: int      # Assign + AugAssign + AnnAssign
    loop_count: int        # For + While
    if_count: int
    # McCabe per function: 1 + every branch (if/elif, for, while, except, and/or each,
    # ternary, comprehension `if`). Module-level CC for flat scripts, same rule.
    cc_per_function: dict[str, int] = field(default_factory=dict)
    cc_module: int = 1
    notes: str = ""


# ── The corpus ──────────────────────────────────────────────────────────────────────

TRUTHS = [
    Truth(
        name="flat_dict_count",
        code=(
            "counts = {}\n"
            'words = ["a", "b", "a"]\n'
            "for word in words:\n"
            "    counts[word] = counts.get(word, 0) + 1\n"
            "print(counts)\n"
        ),
        total_lines=5, blank_lines=0, comment_lines=0,
        lloc=5,                      # assign, assign, for, assign, expr
        functiondef_count=0, class_count=0, return_count=0,
        call_count=2,                # counts.get(...), print(...)
        assign_count=3,              # counts = {}, words = [...], counts[word] = ...
        loop_count=1, if_count=0,
        cc_module=2,                 # 1 + the for
        notes="The archetype: a dictionary, a loop, a print. No function.",
    ),
    Truth(
        name="flat_with_if_and_augassign",
        code=(
            "total = 0\n"
            "for i in range(100):\n"
            "    if i % 3 == 0 or i % 5 == 0:\n"
            "        total += i\n"
            "print(total)\n"
        ),
        total_lines=5, blank_lines=0, comment_lines=0,
        lloc=5,
        functiondef_count=0, class_count=0, return_count=0,
        call_count=2,                # range(...), print(...)
        assign_count=2,              # total = 0, total += i
        loop_count=1, if_count=1,
        cc_module=4,                 # 1 + for + if + or
        notes="`or` is a branch in McCabe: each boolean operator adds one path.",
    ),
    Truth(
        name="one_function_two_branches",
        code=(
            "def classify(n):\n"
            "    if n < 0:\n"
            '        return "neg"\n'
            "    if n == 0:\n"
            '        return "zero"\n'
            '    return "pos"\n'
            "\n"
            "print(classify(5))\n"
        ),
        total_lines=8, blank_lines=1, comment_lines=0,
        lloc=7,                      # def, if, return, if, return, return, expr
        functiondef_count=1, class_count=0, return_count=3,
        call_count=2,                # classify(5), print(...)
        assign_count=0,
        loop_count=0, if_count=2,
        cc_per_function={"classify": 3},   # 1 + if + if
        cc_module=1,
        notes="Two sequential ifs, not nested: CC 3 either way, cognitive treats them alike.",
    ),
    Truth(
        name="nested_loops_in_function",
        code=(
            "def pairs(items):\n"
            "    out = []\n"
            "    for a in items:\n"
            "        for b in items:\n"
            "            if a != b:\n"
            "                out.append((a, b))\n"
            "    return out\n"
        ),
        total_lines=7, blank_lines=0, comment_lines=0,
        lloc=7,
        functiondef_count=1, class_count=0, return_count=1,
        call_count=1,                # out.append(...)
        assign_count=1,              # out = []
        loop_count=2, if_count=1,
        cc_per_function={"pairs": 4},      # 1 + for + for + if
        notes="Nesting does not change McCabe; it does change cognitive complexity.",
    ),
    Truth(
        name="comprehension_with_filter",
        code=(
            "nums = [1, 2, 3, 4, 5, 6]\n"
            "evens = [n for n in nums if n % 2 == 0]\n"
            "print(len(evens))\n"
        ),
        total_lines=3, blank_lines=0, comment_lines=0,
        lloc=3,
        functiondef_count=0, class_count=0, return_count=0,
        call_count=2,                # len(...), print(...)
        assign_count=2,
        loop_count=0,                # a comprehension is not a For node
        if_count=0,                  # nor is its filter an If node
        cc_module=3,                 # 1 + comprehension + its `if` — radon's rule
        notes=(
            "A comprehension is not a loop node, so loop_count stays 0 — but McCabe as "
            "radon implements it counts the comprehension AND its filter as branches."
        ),
    ),
    Truth(
        name="counter_import_and_fstring",
        code=(
            "from collections import Counter\n"
            "\n"
            'text = "hello world"\n'
            "freq = Counter(text)\n"
            "for ch, n in freq.most_common(3):\n"
            '    print(f"{ch}: {n}")\n'
        ),
        total_lines=6, blank_lines=1, comment_lines=0,
        lloc=5,                      # import, assign, assign, for, expr
        functiondef_count=0, class_count=0, return_count=0,
        call_count=3,                # Counter(...), freq.most_common(...), print(...)
        assign_count=2,
        loop_count=1, if_count=0,
        cc_module=2,
        notes="f-strings and imports are common in the corpus and must not confuse counts.",
    ),
    Truth(
        name="comments_and_blanks",
        code=(
            "# compute the sum\n"
            "\n"
            "total = 0  # running total\n"
            "\n"
            "# loop\n"
            "for x in [1, 2, 3]:\n"
            "    total += x\n"
            "print(total)\n"
        ),
        total_lines=8, blank_lines=2, comment_lines=3,   # 2 comment-only + 1 inline
        lloc=4,                      # assign, for, augassign, expr
        functiondef_count=0, class_count=0, return_count=0,
        call_count=1,
        assign_count=2,
        loop_count=1, if_count=0,
        cc_module=2,
        notes="radon's `comments` counts lines *containing* a comment, inline included.",
    ),
    Truth(
        name="class_with_methods",
        code=(
            "class Ledger:\n"
            "    def __init__(self):\n"
            "        self.total = 0\n"
            "\n"
            "    def add(self, n):\n"
            "        if n > 0:\n"
            "            self.total += n\n"
            "        return self.total\n"
        ),
        total_lines=8, blank_lines=1, comment_lines=0,
        lloc=7,                      # class, def, assign, def, if, augassign, return
        functiondef_count=2, class_count=1, return_count=1,
        call_count=0,
        assign_count=2,              # self.total = 0, self.total += n
        loop_count=0, if_count=1,
        cc_per_function={"__init__": 1, "add": 2},
        notes="Methods are FunctionDef nodes; the class body itself adds no branch.",
    ),
    Truth(
        name="while_with_break_and_ternary",
        code=(
            "n = 10\n"
            "steps = 0\n"
            "while n != 1:\n"
            "    n = n // 2 if n % 2 == 0 else 3 * n + 1\n"
            "    steps += 1\n"
            "print(steps)\n"
        ),
        total_lines=6, blank_lines=0, comment_lines=0,
        lloc=6,
        functiondef_count=0, class_count=0, return_count=0,
        call_count=1,
        assign_count=4,              # n=, steps=, n=(ternary), steps+=
        loop_count=1, if_count=0,    # a ternary is IfExp, not If
        cc_module=3,                 # 1 + while + ternary
        notes="A ternary is a branch for McCabe but is not an `if` statement node.",
    ),
    Truth(
        name="try_except",
        code=(
            "try:\n"
            '    value = int("x")\n'
            "except ValueError:\n"
            "    value = 0\n"
            "print(value)\n"
        ),
        total_lines=5, blank_lines=0, comment_lines=0,
        lloc=5,                      # try, assign, except, assign, expr
        functiondef_count=0, class_count=0, return_count=0,
        call_count=2,                # int(...), print(...)
        assign_count=2,
        loop_count=0, if_count=0,
        cc_module=2,                 # 1 + except
        notes="An except handler is a branch: control flow can go two ways.",
    ),
]

IDS = [t.name for t in TRUTHS]


def _independent_depth(tree: ast.AST) -> int:
    """A second, deliberately naive implementation of tree depth — recursive, unlike the
    adapter's iterative one — so the two cannot share a bug."""
    children = list(ast.iter_child_nodes(tree))
    return 1 + max((_independent_depth(c) for c in children), default=0) if children else 0


# ── Line counts: radon ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("truth", TRUTHS, ids=IDS)
def test_radon_line_counts_match_hand_count(truth: Truth):
    values = RadonAdapter().analyse(truth.code).values
    assert values["total_lines"] == truth.total_lines
    assert values["blank_lines"] == truth.blank_lines
    assert values["comments"] == truth.comment_lines
    assert values["lloc"] == truth.lloc, truth.notes


# ── Structural counts: ast adapter ──────────────────────────────────────────────────


@pytest.mark.parametrize("truth", TRUTHS, ids=IDS)
def test_ast_counts_match_hand_count(truth: Truth):
    values = AstAdapter().analyse(truth.code).values
    assert values["functiondef_count"] == truth.functiondef_count
    assert values["class_count"] == truth.class_count
    assert values["return_count"] == truth.return_count
    assert values["call_count"] == truth.call_count
    assert values["assign_count"] == truth.assign_count
    tree = ast.parse(truth.code)
    nodes = list(ast.walk(tree))
    assert values["total_nodes"] == len(nodes)
    loops = sum(isinstance(n, (ast.For, ast.While, ast.AsyncFor)) for n in nodes)
    ifs = sum(isinstance(n, ast.If) for n in nodes)
    assert loops == truth.loop_count, truth.notes
    assert ifs == truth.if_count, truth.notes
    assert values["loop_ratio"] == pytest.approx(loops / len(nodes), abs=1e-6)


@pytest.mark.parametrize("truth", TRUTHS, ids=IDS)
def test_ast_depth_agrees_with_an_independent_recursive_count(truth: Truth):
    """Two implementations that share nothing but the definition."""
    values = AstAdapter().analyse(truth.code).values
    assert values["ast_depth"] == _independent_depth(ast.parse(truth.code))


# ── McCabe: three engines against the hand count ────────────────────────────────────


@pytest.mark.parametrize("truth", TRUTHS, ids=IDS)
def test_radon_cyclomatic_complexity_matches_hand_count(truth: Truth):
    """The thesis's primary complexity metric, checked against a person counting branches."""
    from radon.complexity import ComplexityVisitor

    visitor = ComplexityVisitor.from_code(truth.code)
    per_function = {
        b.name: b.complexity for b in visitor.blocks if b.name in truth.cc_per_function
    }

    for name, expected in truth.cc_per_function.items():
        assert per_function.get(name) == expected, f"{truth.name}: {name} — {truth.notes}"

    if not truth.cc_per_function:
        # Flat script: the module body is the block, and the adapter imputes it.
        values = RadonAdapter().analyse(truth.code).values
        assert values["cc_imputed_module_level"] is True
        assert values["cyclomatic_complexity_mean"] == truth.cc_module, truth.notes


WITH_FUNCTIONS = [t for t in TRUTHS if t.cc_per_function]


@pytest.mark.parametrize("truth", WITH_FUNCTIONS, ids=[t.name for t in WITH_FUNCTIONS])
def test_lizard_cyclomatic_complexity_matches_hand_count(truth: Truth):
    """A second, independent McCabe implementation against the same hand count.

    lizard tokenises rather than walking an AST, so it shares no code with radon. Where
    both match the hand count, the count is very probably right; where they split, the
    hand count is the tie-breaker and the loser has a documented quirk.
    """
    import lizard

    analysed = lizard.analyze_file.analyze_source_code("f.py", truth.code)
    per_function = {
        f.name.split("::")[-1]: f.cyclomatic_complexity for f in analysed.function_list
    }
    for name, expected in truth.cc_per_function.items():
        assert per_function.get(name) == expected, f"{truth.name}: {name} — {truth.notes}"


# ── Cognitive complexity: hand-derived from Sonar's rules ───────────────────────────

COGNITIVE = {
    # Sonar: +1 per control structure, +1 more per level of nesting, +1 per sequence of
    # boolean operators. Sequential ifs at the same level: +1 each. Nested: +nesting.
    "one_function_two_branches": {"classify": 2},   # if(+1) + if(+1), no nesting
    "nested_loops_in_function": {"pairs": 6},       # for(+1) + for(+1,+1 nest) + if(+1,+2 nest)
    "class_with_methods": {"__init__": 0, "add": 1},
}


@pytest.mark.parametrize("name", list(COGNITIVE), ids=list(COGNITIVE))
def test_cognitive_complexity_matches_hand_derivation(name: str):
    truth = next(t for t in TRUTHS if t.name == name)
    adapter = ComplexipyAdapter()
    result = adapter.analyse(truth.code)
    got = {
        f["name"].split("::")[-1]: f["cognitive_complexity"] for f in result.functions
    }
    for fn, expected in COGNITIVE[name].items():
        assert got.get(fn) == expected, f"{name}: {fn} — nesting increments per Sonar"


# ── Halstead: no oracle, so pin the operator tables instead ─────────────────────────


def test_halstead_operator_tables_are_documented():
    """There is no correct Halstead volume for Python, so this does not assert one.

    It asserts the thing that *is* knowable: what each engine counts as an operator, on a
    fragment where the answer is legible. A reader can then decide which definition suits
    their question, which is the only honest thing a tool can offer here.
    """
    code = (
        "def f(a, b):\n"
        "    if a > b:\n"
        "        return a + b\n"
        "    return b - a\n"
    )
    import lizard
    from radon.metrics import h_visit

    radon_total = h_visit(code).total
    analyzer = lizard.FileAnalyzer(lizard.get_extensions(["halstead"]))
    analysed = analyzer.analyze_source_code("f.py", code)
    lizard_fn = analysed.function_list[0]

    # radon: only BinOp, UnaryOp, BoolOp, AugAssign, Compare. Here that is `>`, `+`, `-`.
    assert radon_total.h1 == 3
    # lizard: a token-level definition that also counts keywords and punctuation as
    # operators — def, if, return, the parentheses, the colon, and so on.
    assert lizard_fn.halstead_n1 > radon_total.h1

    # The operands, by contrast, agree: both see a, b, f and the parameter names.
    assert lizard_fn.halstead_n2 == radon_total.h2

    # So the whole volume disagreement is in the operator table, and that is documented
    # in docs/motivation.md §2.2 rather than resolved by fiat.
