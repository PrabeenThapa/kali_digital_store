import asyncio
import logging
from dotenv import load_dotenv

load_dotenv(encoding="utf-8")

from notify_bot.main import start_notify_bot

if __name__ == "__main__":
    try:
        asyncio.run(start_notify_bot())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Notify bot stopped.")

# Also callable when run as module entry point (python -m notify_bot.run)
asyncio.run(start_notify_bot()) if __name__ != "__main__" else None
