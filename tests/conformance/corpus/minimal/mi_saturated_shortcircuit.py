"""Pins maintainability-index saturation through path 1, the short circuit.

Every operation here is a call, a subscript or an assignment. radon's HalsteadVisitor
recognises none of those, so it reports zero distinct operators, and Halstead volume comes
out at exactly zero. mi_compute then returns 100.0 without computing anything:

    if any(metric <= 0 for metric in (halstead_volume, sloc)):
        return 100.0

Note how little it takes: adding a single `+ 1` to the counter would give radon a BinOp,
make the volume positive, and drop the index to the mid-nineties. The saturation is that
brittle, and that is why it is invisible without a flag.

Expected: halstead_volume == 0, maintainability_index == 100.0,
maintainability_index_saturated is True, maintainability_saturation_path == 1.
"""

counts = {}
words = ["alpha", "beta", "alpha"]
for word in words:
    counts.setdefault(word, []).append(word)
print(counts)
