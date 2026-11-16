import unittest

from shop.cart import cart_total
from shop.invoice import render
from shop.shipping import ship_cost


class Base(unittest.TestCase):
    def test_cart_total(self):
        self.assertEqual(cart_total([("apple", 2), ("pear", 1)]), 4.5)

    def test_render(self):
        self.assertEqual(render([("plum", 4)]), "plum x4: 2.00")

    def test_ship(self):
        self.assertEqual(ship_cost(3), 5.0)
