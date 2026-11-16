from shop.pricing import price


def cart_total(lines):
    return round(sum(price(item, qty) for item, qty in lines), 2)
