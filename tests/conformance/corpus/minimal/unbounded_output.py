"""A fragment that would print forever if executed.

This package performs static analysis and never executes what it measures, so this file is
inert here. It is kept because any future execution-based feature must not regress into
buffered output capture: capture_output=True holds everything the child writes, and a loop
like this one accumulated hundreds of megabytes per second in a parent process until the
container was OOM-killed.

The bounded drain in execution.py is the standing answer. This fragment is the reminder of
why it is not over-engineering.

Expected: analysed normally, like any other valid fragment.
"""

while True:
    print("x" * 1024)
