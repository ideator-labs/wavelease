PRICES = {"apple": 1.25, "pear": 2.0, "plum": 0.5}


def price(item, qty):
    return round(PRICES[item] * qty, 2)
