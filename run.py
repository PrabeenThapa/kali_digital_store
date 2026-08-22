import asyncio
import logging
from dotenv import load_dotenv

from apps.telegram_bot.main import start_bot

load_dotenv(encoding='utf-8')

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped.")
