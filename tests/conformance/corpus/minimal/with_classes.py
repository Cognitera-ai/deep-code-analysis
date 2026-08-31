"""Exercises the OO design metrics, which only pyscn provides for Python.

`Ledger` has two attribute groups that never interact: the balance methods touch
`self.balance`, and `describe` touches nothing at all. LCOM4 counts connected components of
the method-attribute graph, so this class is not cohesive and LCOM4 should exceed 1.

Expected: class_count == 1, lcom_mean > 1, and every OO column is non-null. For a fragment
with no classes those same columns must be null rather than zero — that contrast is the
point of keeping this file alongside flat_script.py.
"""


class Ledger:
    def __init__(self):
        self.balance = 0
        self.history = []

    def deposit(self, amount):
        if amount > 0:
            self.balance += amount
            self.history.append(amount)
        return self.balance

    def withdraw(self, amount):
        if 0 < amount <= self.balance:
            self.balance -= amount
            self.history.append(-amount)
        return self.balance

    def describe(self):
        return "a ledger"
