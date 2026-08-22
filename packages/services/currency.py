"""
Currency service — single source of truth for currency display and conversion.

Add new currencies by extending CURRENCY_SYMBOLS and, if needed, CONVERSION_RATES.
Handlers must never hardcode currency symbols or conversion factors.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from packages.config.config import EnvKeys

# Display symbols for known currencies
CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "RUB": "₽",
    "EUR": "€",
    "USDT": "$",
}

# Static fallback conversion rates relative to USD.
# In production these should come from a live exchange API.
# Rates here are defaults only; override via ENV if needed.
_FALLBACK_RATES_TO_USD: dict[str, Decimal] = {
    "USD":  Decimal("1"),
    "USDT": Decimal("1"),
    "RUB":  Decimal("0.011"),   # ~1 RUB = 0.011 USD
    "EUR":  Decimal("1.08"),
}


def currency_symbol(currency: Optional[str] = None) -> str:
    """Return the display symbol for *currency* (defaults to PAY_CURRENCY)."""
    code = (currency or EnvKeys.PAY_CURRENCY).upper()
    return CURRENCY_SYMBOLS.get(code, code)


def format_amount(amount: Decimal | float | int,
                  currency: Optional[str] = None) -> str:
    """Format *amount* with the currency symbol, e.g. '$14.99' or '₽1 350'."""
    code = (currency or EnvKeys.PAY_CURRENCY).upper()
    symbol = CURRENCY_SYMBOLS.get(code, code + " ")
    dec = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if code == "RUB":
        # Russian convention: spaces as thousands separator, no decimals for round numbers
        int_part = int(dec)
        frac = dec - int_part
        formatted = f"{int_part:,}".replace(",", " ")
        if frac:
            formatted += str(frac)[1:]   # append '.xx'
        return f"{formatted} {symbol}"
    return f"{symbol}{dec}"


def convert(amount: Decimal | float | int,
            from_currency: str,
            to_currency: str) -> Decimal:
    """
    Convert *amount* from *from_currency* to *to_currency* using fallback rates.
    Raises ValueError if either currency is unknown.
    """
    src = from_currency.upper()
    dst = to_currency.upper()
    if src == dst:
        return Decimal(str(amount)).quantize(Decimal("0.0001"))

    rate_src = _FALLBACK_RATES_TO_USD.get(src)
    rate_dst = _FALLBACK_RATES_TO_USD.get(dst)

    if rate_src is None:
        raise ValueError(f"Unknown source currency: {src}")
    if rate_dst is None:
        raise ValueError(f"Unknown target currency: {dst}")

    usd_amount = Decimal(str(amount)) * rate_src
    result = (usd_amount / rate_dst).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    return result


def pay_currency() -> str:
    """Return the configured payment currency code (PAY_CURRENCY env)."""
    return EnvKeys.PAY_CURRENCY.upper()
