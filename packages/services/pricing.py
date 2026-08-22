import math
from decimal import Decimal


def calculate_sell_price(cost_price: float | Decimal | int, markup_percent: float | Decimal | int = 30.0) -> float:
    """
    Calculate selling price with minimum 30% margin over base cost price,
    automatically increased to the nearest 0.25 step (0.00, 0.25, 0.50, 0.75, integer).
    """
    try:
        cost = float(cost_price)
    except (ValueError, TypeError):
        return 0.0
    if cost <= 0:
        return 0.0
    try:
        markup = float(markup_percent)
    except (ValueError, TypeError):
        markup = 30.0

    # Ensure minimum 30% margin
    effective_markup = max(markup, 30.0)
    raw_price = cost * (1.0 + effective_markup / 100.0)

    # Automatically round UP to the nearest 0.25 step (e.g. .00, .25, .50, .75)
    stepped_price = math.ceil(round(raw_price, 4) * 4.0) / 4.0
    return round(stepped_price, 2)


def apply_promo_discount(price: Decimal, promo_data: dict) -> Decimal:
    """Apply a promo code discount to a price. Returns the discounted unit price."""
    if not promo_data:
        return price
    discount_type = promo_data.get('discount_type', '')
    discount_value = Decimal(str(promo_data.get('discount_value', 0)))
    if discount_type == 'percent':
        discount = price * discount_value / 100
    else:
        discount = min(discount_value, price)
    return (price - discount).quantize(Decimal("0.01"))


def apply_account_discount(price: Decimal, discount_percent: float) -> Decimal:
    """Apply the user's account-level percentage discount."""
    if not discount_percent:
        return price
    discount = price * Decimal(str(discount_percent)) / 100
    return (price - discount).quantize(Decimal("0.01"))
