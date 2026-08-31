# Minimal conformance corpus

One fragment per known pathology. Each file's docstring says which case it pins and what
the engines are expected to do with it, so a diff in the golden files points at a specific
behaviour rather than an anonymous number.

These are deliberately small and hand-written. The `humaneval` and `generated` tiers exist
for external comparability and for realism; this tier exists so CI can run the whole
divergence machinery in under a second and so a regression names itself.

Files whose name starts with `invalid_` are **not** valid Python. That is the point of
them, and the loader must not try to import anything here.
