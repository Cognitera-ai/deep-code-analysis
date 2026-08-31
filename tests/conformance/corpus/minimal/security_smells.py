"""Exercises bandit across both of its axes.

bandit reports severity and confidence independently, and this fragment deliberately mixes
them: `eval` on external input is high severity and high confidence, while `md5` is a weaker
finding. Collapsing the two axes into one score would lose the distinction bandit went to
the trouble of making, which is why the adapter emits both.

Relevant to generated code specifically: models reproduce insecure idioms from training
data, so these counts are a response variable rather than a hygiene check.

Expected: security_issues > 0, with at least one non-zero severity and confidence bucket.
"""

import hashlib
import subprocess


def run_it(user_input, command):
    digest = hashlib.md5(user_input.encode()).hexdigest()
    result = eval(user_input)  # noqa: S307 - deliberate, this file is a fixture
    subprocess.call(command, shell=True)
    return digest, result
