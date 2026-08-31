"""A fragment where the maintainability index actually carries information.

Arithmetic and comparisons give radon operators to count, so volume is positive and the
index is computed rather than short-circuited. This is the control case: without it, a
regression that made every fragment saturate would look like correct behaviour.

Expected: halstead_volume > 0, maintainability_index < 100,
maintainability_saturation_path == 0.
"""


def score(values, weights):
    total = 0.0
    for index, value in enumerate(values):
        if index < len(weights) and value > 0:
            total += value * weights[index] - (value / 2.0)
        elif value < 0:
            total -= value * 1.5
    return total / len(values) if values else 0.0
