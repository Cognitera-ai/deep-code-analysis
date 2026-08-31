"""Pins the AST-depth computation against stack exhaustion.

A literal nested 200 levels deep. The adapter walks it iteratively, so its cost is
independent of depth; a recursive walk consumes one stack frame per level and its safety
margin depends on the interpreter's recursion limit, which a caller can lower and an
embedding host often has.

This is not a hypothetical hazard. A deeply nested but entirely valid generated fragment
once raised RecursionError inside a depth computation and aborted a whole export, losing
every fragment measured up to that point. Losing thousands of measurements to one
pathological input is the failure mode ADR-0013 exists to prevent, and
``test_depth_is_independent_of_the_recursion_limit`` demonstrates the difference directly.

Generated code reaches this shape more often than hand-written code, through repeated
"handle one more case" continuations.

Expected: ast_depth is a large finite integer, no exception, no degradation recorded.
"""

v = [[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[[1]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]
