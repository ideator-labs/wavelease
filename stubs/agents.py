"""STUB coding agents. Each one stands in for a real coding agent (Claude Code, Codex, Cursor...)
working on one task in its own git worktree. They are scripted edits, not models.

Like a real agent, a stub reads the code at the base it was given: T2 and T4 look up price()'s
current signature in their own worktree and call it accordingly. That is the whole point: an agent
can only adapt to a contract change that is already in its base.
"""
import ast
import re
from pathlib import Path


def _price_takes_currency(wt):
    tree = ast.parse((wt / "shop/pricing.py").read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "price")
    return "currency" in [a.arg for a in fn.args.args]


def _price_call(wt, item, qty):
    return f'price({item}, {qty}, "USD")' if _price_takes_currency(wt) else f"price({item}, {qty})"


def _append(path, text):
    path.write_text(path.read_text().rstrip("\n") + "\n" + text)


def t1(wt):
    p = wt / "shop/pricing.py"
    s = p.read_text().replace(
        "def price(item, qty):\n    return round(PRICES[item] * qty, 2)",
        'RATES = {"USD": 1.0, "EUR": 0.9}\n\n\n'
        "def price(item, qty, currency):\n    return round(PRICES[item] * qty * RATES[currency], 2)")
    p.write_text(s)
    for caller in ("shop/cart.py", "shop/invoice.py"):  # update the call sites it can see
        f = wt / caller
        f.write_text(re.sub(r"price\(item, qty\)", 'price(item, qty, "USD")', f.read_text()))
    (wt / "tests/test_t1.py").write_text(
        "import unittest\n\nfrom shop.pricing import price\n\n\n"
        "class T1(unittest.TestCase):\n    def test_eur(self):\n"
        '        self.assertEqual(price("pear", 2, "EUR"), 3.6)\n')


def t2(wt):
    _append(wt / "shop/cart.py",
            "\n\ndef bulk_total(lines, threshold=10):\n"
            f"    return round(sum({_price_call(wt, 'item', 'qty')} * (0.9 if qty >= threshold else 1.0)\n"
            "                     for item, qty in lines), 2)\n")
    (wt / "tests/test_t2.py").write_text(
        "import unittest\n\nfrom shop.cart import bulk_total\n\n\n"
        "class T2(unittest.TestCase):\n    def test_bulk(self):\n"
        '        self.assertEqual(bulk_total([("plum", 20), ("pear", 1)]), 11.0)\n')


def t3(wt, stray=False):
    _append(wt / "shop/shipping.py",
            "\n\ndef free_over(weight_kg, limit=50):\n    return 0.0 if weight_kg > limit else ship_cost(weight_kg)\n")
    (wt / "tests/test_t3.py").write_text(
        "import unittest\n\nfrom shop.shipping import free_over\n\n\n"
        "class T3(unittest.TestCase):\n    def test_free(self):\n"
        "        self.assertEqual(free_over(60), 0.0)\n")
    if stray:  # wanders outside its task: "tidies" a file another agent holds
        _append(wt / "shop/pricing.py", "\n# TODO(T3): move PRICES to a config file\n")


def t4(wt):
    _append(wt / "shop/invoice.py",
            "\n\ndef tax_line(lines, rate=0.1):\n"
            f"    tax = sum({_price_call(wt, 'item', 'qty')} for item, qty in lines) * rate\n"
            '    return f"tax: {tax:.2f}"\n')
    (wt / "tests/test_t4.py").write_text(
        "import unittest\n\nfrom shop.invoice import tax_line\n\n\n"
        "class T4(unittest.TestCase):\n    def test_tax(self):\n"
        '        self.assertEqual(tax_line([("pear", 5)]), "tax: 1.00")\n')


AGENTS = {"T1": t1, "T2": t2, "T3": t3, "T4": t4}


def run(task_id, worktree, stray=False):
    wt = Path(worktree)
    fn = AGENTS[task_id]
    fn(wt, stray=True) if (stray and task_id == "T3") else fn(wt)
