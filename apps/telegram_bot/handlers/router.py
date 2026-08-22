from aiogram import Dispatcher

from apps.telegram_bot.handlers.admin import router as admin_router
from apps.telegram_bot.handlers.other import router as other_router
from apps.telegram_bot.handlers.user import router as user_router


def register_all_handlers(dp: Dispatcher) -> None:
    """Include all feature routers into the dispatcher."""
    dp.include_router(admin_router)
    dp.include_router(other_router)
    dp.include_router(user_router)
