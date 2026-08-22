import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

from notify_bot.main import start_notify_bot

try:
    asyncio.run(start_notify_bot())
except (KeyboardInterrupt, SystemExit):
    logging.info("Notify bot stopped.")
