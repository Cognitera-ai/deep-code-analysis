"""Pins radon's Halstead blindness — the package's founding observation.

This fragment has obvious computational content: five calls, four assignments, a loop, a
list literal, a method call. radon recognises none of it as an operator, because its
HalsteadVisitor implements only visit_BinOp, visit_UnaryOp, visit_BoolOp, visit_AugAssign
and visit_Compare. It therefore reports volume 0.

lizard, measuring the same fragment, reports a positive volume.

Expected: radon volume == 0, lizard volume > 0, and halstead_volume__divergent is True by
the zero-versus-non-zero rule. This is the shape of ~70 % of real LLM-generated code.
"""


def sum_of_multiples(limit, divisors):
    multiples = set()
    for divisor in divisors:
        multiples.update(range(divisor, limit, divisor))
    return sum(multiples)


limit = 65536
divisors = [3, 8]
result = sum_of_multiples(limit, divisors)
print(result)
