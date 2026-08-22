import asyncio
from typing import List, Optional, Callable, Awaitable, Union
from dataclasses import dataclass
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest

from apps.telegram_bot.core.logging import logger


@dataclass
class BroadcastStats:
    """Statistics collected during a broadcast run."""

    total: int = 0
    sent: int = 0
    failed: int = 0
    blocked: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.sent / self.total) * 100

    @property
    def duration(self) -> Optional[float]:
        if not self.start_time or not self.end_time:
            return None
        return (self.end_time - self.start_time).total_seconds()


class BroadcastManager:
    """Manager for mass messaging with rate-limiting and retry logic."""

    def __init__(
        self,
        bot: Bot,
        batch_size: int = 30,
        batch_delay: float = 1.0,
        retry_count: int = 3,
    ):
        self.bot = bot
        self.batch_size = batch_size
        self.batch_delay = batch_delay
        self.retry_count = retry_count
        self._cancelled = False

    async def _send_message_safe(
        self,
        user_id: int,
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML",
    ) -> bool:
        """Send a single message with retry on flood-control and error handling."""
        for attempt in range(self.retry_count):
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode,
                    disable_notification=True,
                )
                return True
            except TelegramRetryAfter as e:
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(e.retry_after)
                    continue
                return False
            except TelegramForbiddenError:
                logger.debug(f"Bot blocked by user {user_id}")
                return False
            except TelegramBadRequest as e:
                logger.error(f"Bad request for user {user_id}: {e}")
                return False
            except Exception as e:
                logger.error(f"Unknown error sending to {user_id}: {e}")
                if attempt < self.retry_count - 1:
                    await asyncio.sleep(1)
                    continue
                return False
        return False

    async def broadcast(
        self,
        user_ids: List[int],
        text: str,
        reply_markup: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = "HTML",
        progress_callback: Optional[Union[
            Callable[["BroadcastStats"], None],
            Callable[["BroadcastStats"], Awaitable[None]],
        ]] = None,
    ) -> BroadcastStats:
        """Send a message to all given user IDs in rate-limited batches."""
        stats = BroadcastStats(total=len(user_ids), start_time=datetime.now())
        self._cancelled = False

        for i in range(0, len(user_ids), self.batch_size):
            if self._cancelled:
                logger.info("Broadcast cancelled")
                break

            batch = user_ids[i: i + self.batch_size]
            tasks = [self._send_message_safe(uid, text, reply_markup, parse_mode) for uid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    stats.failed += 1
                elif result:
                    stats.sent += 1
                else:
                    stats.failed += 1

            if progress_callback:
                try:
                    if asyncio.iscoroutinefunction(progress_callback):
                        await progress_callback(stats)
                    else:
                        progress_callback(stats)
                except Exception as e:
                    logger.error(f"Progress callback error: {e}")

            if i + self.batch_size < len(user_ids):
                await asyncio.sleep(self.batch_delay)

        stats.end_time = datetime.now()
        stats.blocked = stats.failed
        return stats

    def cancel(self):
        """Signal the running broadcast to stop after the current batch."""
        self._cancelled = True
