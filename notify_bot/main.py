"""
Admin Notification Bot — Main startup
Minimal polling bot with no middleware overhead.
"""
import asyncio
import logging
import sys
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

from packages.config.config import EnvKeys
from packages.database.models import register_models
from notify_bot.handlers import router


async def start_notify_bot() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] notify_bot: %(message)s",
    )

    if not EnvKeys.NOTIFY_BOT_TOKEN:
        logging.critical("NOTIFY_BOT_TOKEN is not set — admin notification bot cannot start.")
        sys.exit(1)

    if not EnvKeys.OWNER_ID:
        logging.critical("OWNER_ID is not set — admin notification bot cannot start.")
        sys.exit(1)

    await register_models()

    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    async with Bot(
        token=EnvKeys.NOTIFY_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode="HTML"),
    ) as bot:
        bot_info = await bot.get_me()
        logging.info(f"Notify bot started: @{bot_info.username} (ID: {bot_info.id})")

        # Greet admin on startup
        try:
            await bot.send_message(
                chat_id=EnvKeys.OWNER_ID,
                text=(
                    "🔔 <b>Notification Bot Online</b>\n\n"
                    "Payment approval requests will appear here.\n"
                    "Both this bot and the main shop bot will send you notifications."
                ),
            )
        except Exception as e:
            logging.warning(f"Could not send startup message to admin: {e}. "
                            "Make sure you've started a chat with the notify bot first.")

        await dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query"],
            handle_signals=True,
        )
