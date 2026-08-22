from decimal import Decimal
from typing import Optional, Annotated, Self
from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator
import re


class PaymentRequest(BaseModel):
    """Validate payment request data."""

    amount: Decimal = Field(..., gt=0, le=100000)
    currency: str = Field(..., min_length=3, max_length=3)
    provider: str = Field(..., pattern="^(telegram|stars|cryptopay|fiat|bybit|bybit_uid|binance_uid)$")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount can have maximum 2 decimal places")
        return v


class ItemPurchaseRequest(BaseModel):
    """Validate item purchase request."""

    item_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    user_id: int = Field(..., gt=0)

    @field_validator("item_name")
    @classmethod
    def validate_item_name(cls, v: str) -> str:
        if re.search(r"[\x00-\x1f\x7f]", v):
            raise ValueError("Invalid characters in item name")
        return v


class UserDataUpdate(BaseModel):
    """Validate user data updates."""

    telegram_id: int = Field(..., gt=0)
    new_balance: Optional[Decimal] = Field(None, ge=0)
    new_role: Optional[str] = Field(None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if self.new_balance is None and self.new_role is None:
            raise ValueError("At least one field to update must be provided")
        return self


class CategoryRequest(BaseModel):
    """Validate category management requests."""

    name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        # Only block actual control characters — allow emojis and Unicode
        if re.search(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", v):
            raise ValueError("Invalid characters in category name")
        return v

    def sanitize_name(self) -> str:
        """Return category name stripped of HTML tags and collapsed whitespace."""
        cleaned = re.sub(r"<[^>]+>", "", self.name)
        return " ".join(cleaned.split())


class BroadcastMessage(BaseModel):
    """Validate broadcast message data."""

    text: Annotated[str, StringConstraints(min_length=1, max_length=4096, strip_whitespace=True)]
    parse_mode: str = Field("HTML", pattern="^(HTML|Markdown|MarkdownV2)$")

    @field_validator("text")
    @classmethod
    def validate_text(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 4096:
            raise ValueError("Message text is too long (max 4096 bytes)")
        # Validate balanced basic HTML tags if present
        for tag in ["b", "i", "code", "s", "u", "pre"]:
            if v.count(f"<{tag}>") != v.count(f"</{tag}>"):
                raise ValueError(f"Unbalanced <{tag}> tag in broadcast message")
        return v


class SearchQuery(BaseModel):
    """Validate search query."""

    query: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    page: int = Field(0, ge=0)
    per_page: int = Field(10, ge=1, le=100)


class PromoCodeRequest(BaseModel):
    """Validate promo code creation/update data."""

    code: Annotated[str, StringConstraints(min_length=1, max_length=50, strip_whitespace=True)]
    discount_type: str = Field(..., pattern="^(percent|fixed|balance)$")
    discount_value: Decimal = Field(..., gt=0)
    max_uses: int = Field(0, ge=0)


class ReviewRequest(BaseModel):
    """Validate review submission."""

    item_name: Annotated[str, StringConstraints(min_length=1, max_length=100, strip_whitespace=True)]
    rating: int = Field(..., ge=1, le=5)
    text: Optional[Annotated[str, StringConstraints(max_length=1000, strip_whitespace=True)]] = None


# ── Utility functions ────────────────────────────────────────────────────── #

def validate_telegram_id(telegram_id: str | int) -> int:
    """Return a valid Telegram ID integer or raise ValueError."""
    if telegram_id is None:
        raise ValueError("Telegram ID cannot be None")
    try:
        tid = int(telegram_id)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid Telegram ID: {telegram_id}")
    if tid <= 0 or tid > 9999999999:
        raise ValueError(f"Telegram ID out of valid range: {tid}")
    return tid


def validate_money_amount(
    amount: str | int | float | Decimal,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
) -> Decimal:
    """Parse and validate a monetary amount, returning Decimal or raising ValueError.

    Args:
        amount: The raw amount value to parse.
        min_amount: Optional lower bound (inclusive).
        max_amount: Optional upper bound (inclusive).
    """
    if amount is None:
        raise ValueError("Amount cannot be None")
    try:
        value = Decimal(str(amount))
    except Exception:
        raise ValueError(f"Invalid monetary amount: {amount}")
    if value <= 0:
        raise ValueError(f"Amount must be positive: {value}")
    if value.as_tuple().exponent < -2:
        value = value.quantize(Decimal("0.01"))
    if min_amount is not None and value < min_amount:
        raise ValueError(f"Amount {value} below minimum {min_amount}")
    if max_amount is not None and value > max_amount:
        raise ValueError(f"Amount {value} above maximum {max_amount}")
    return value


def sanitize_html(text: str) -> str:
    """
    Escape HTML special characters while preserving safe Telegram tags.
    """
    if not text:
        return ""
    safe_tags = ["b", "i", "code", "s", "u", "pre"]
    placeholders = {}
    for i, tag in enumerate(safe_tags):
        open_tag = f"<{tag}>"
        close_tag = f"</{tag}>"
        if open_tag in text:
            ph_open = f"__SAFE_OPEN_{i}__"
            placeholders[ph_open] = open_tag
            text = text.replace(open_tag, ph_open)
        if close_tag in text:
            ph_close = f"__SAFE_CLOSE_{i}__"
            placeholders[ph_close] = close_tag
            text = text.replace(close_tag, ph_close)

    text = (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

    for ph, tag in placeholders.items():
        text = text.replace(ph, tag)

    return text
