"""The CK inheritance metrics: DIT, NOC, RFC.

These exist for Java and C#. The only tool that computed them for Python is EUPL-licensed,
written in C++, and untouched since 2022 — so they are computed here from the syntax tree,
under the same sanctioned exception as the other AST metrics (ADR-0001).
"""

from __future__ import annotations

from dca.adapters.ast_adapter import AstAdapter

HIERARCHY = """
class Base:
    def run(self):
        return helper(1)


class Mid(Base):
    def run(self):
        return other(2)

    def extra(self):
        return 3


class Leaf(Mid):
    def go(self):
        return self.run()
"""


def test_depth_follows_the_local_chain():
    values = AstAdapter().analyse(HIERARCHY).values
    assert values["class_count"] == 3
    assert values["dit_max"] == 3       # Base -> Mid -> Leaf
    assert values["dit_mean"] == 2.0    # 1, 2, 3


def test_a_class_with_an_imported_base_is_depth_one_and_counted_as_external():
    """The honest limit of measuring one fragment: a base in another module is invisible,
    so the chain stops. Reporting depth 1 silently would hide that; the external count is
    what lets a reader tell a flat hierarchy from one that is merely out of view."""
    values = AstAdapter().analyse("class Thing(SomeImportedBase):\n    pass\n").values

    assert values["dit_max"] == 1
    assert values["base_classes_external"] == 1


def test_object_is_not_counted_as_an_external_base():
    """Every class inherits from object implicitly; counting it would make the column
    a constant."""
    values = AstAdapter().analyse("class Thing(object):\n    pass\n").values
    assert values["base_classes_external"] == 0


def test_number_of_children_counts_direct_subclasses():
    code = "class P:\n    pass\nclass A(P):\n    pass\nclass B(P):\n    pass\n"
    assert AstAdapter().analyse(code).values["noc_max"] == 2


def test_response_for_a_class_counts_methods_plus_what_they_call():
    values = AstAdapter().analyse(HIERARCHY).values
    # Mid defines run and extra, and calls other(): 2 + 1.
    assert values["rfc_max"] >= 3


def test_ck_metrics_are_null_without_classes():
    """A semantic null. 'No classes' is not 'inheritance depth zero'."""
    values = AstAdapter().analyse("x = 1\nprint(x)\n").values

    assert values["class_count"] == 0
    for key in ("dit_max", "dit_mean", "noc_max", "rfc_max", "methods_per_class_mean"):
        assert values[key] is None, key


def test_a_cyclic_definition_does_not_hang():
    """A fragment need not be importable, so the class graph need not be acyclic."""
    code = "class A(B):\n    pass\nclass B(A):\n    pass\n"
    values = AstAdapter().analyse(code).values
    assert values["dit_max"] >= 1
