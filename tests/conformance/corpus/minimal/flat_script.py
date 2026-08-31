"""Pins the flat-script case, which drives two separate behaviours.

No function is defined, so:

* radon reports no per-block cyclomatic complexity, and the adapter imputes the module
  body's complexity with cc_imputed_module_level set (R-04). Leaving it null would make the
  missingness a treatment effect, since smaller models write flat scripts far more often.
* lizard reports nothing at all — its per-function metrics, Halstead included, have no
  functions to measure. This is exactly why lizard cannot replace radon for Halstead: on a
  corpus that is mostly flat scripts, switching engines trades zeros for nulls.

Expected: cc_imputed_module_level is True; every lizard per-function column is null, not
zero.
"""

total = 0
for i in range(100):
    if i % 3 == 0 or i % 5 == 0:
        total += i
print(total)
