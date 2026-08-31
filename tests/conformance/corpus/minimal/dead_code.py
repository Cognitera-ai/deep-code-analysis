"""Exercises the two dead-code detectors, which deliberately disagree.

`unreachable` has a statement after an unconditional return: pyscn finds it through the
control-flow graph. `never_called` is defined and never referenced: vulture finds it through
name resolution. Neither tool finds the other's case.

The adapters do not reconcile them (R-22). They answer different questions, and their
disagreement is a datum rather than a bug.

Expected: dead_code_findings__pyscn > 0 and dead_code_items__vulture > 0, with no attempt
made to make them agree.
"""


def unreachable(value):
    return value
    print("this line can never run")


def never_called():
    return 42
