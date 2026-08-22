from dataclasses import dataclass

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from packages.database.methods import check_role_cached
from packages.config.config import EnvKeys


@dataclass
class ValidAmountFilter(BaseFilter):
    """Validates that a message contains a number within the configured payment range.
    Accepts integers and decimals (e.g. 10, 10.5, 10.50).
    """

    min_amount: int = EnvKeys.MIN_AMOUNT
    max_amount: int = EnvKeys.MAX_AMOUNT

    async def __call__(self, message: Message) -> bool:
        from decimal import Decimal, InvalidOperation
        text: str = (message.text or "").strip().replace(",", ".")
        try:
            value = Decimal(text)
        except InvalidOperation:
            return False
        if value <= 0:
            return False
        return Decimal(str(self.min_amount)) <= value <= Decimal(str(self.max_amount))


@dataclass
class HasPermissionFilter(BaseFilter):
    """
    Filter: all specified permission bits must be set (AND semantics).
    Uses bit-mask from the user's role.
    """

    permission: int

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_permissions: int = await check_role_cached(event.from_user.id) or 0
        return (user_permissions & self.permission) == self.permission


@dataclass
class HasAnyPermissionFilter(BaseFilter):
    """
    Filter: at least one of the specified permission bits must be set (OR semantics).
    """

    permissions: int

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user_permissions: int = await check_role_cached(event.from_user.id) or 0
        return (user_permissions & self.permissions) != 0
