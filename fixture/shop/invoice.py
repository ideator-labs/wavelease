from shop.pricing import price


def render(lines):
    rows = [f"{item} x{qty}: {price(item, qty):.2f}" for item, qty in lines]
    return "\n".join(rows)
