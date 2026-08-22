# bot/handlers/__init__.py
from apps.telegram_bot.handlers.router import register_all_handlers

__all__ = ["register_all_handlers"]
