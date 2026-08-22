import asyncio
from datetime import datetime

from apps.telegram_bot.cache.manager import get_cache_manager
from apps.telegram_bot.core.logging import logger


async def _redis_health_monitor():
    """Monitor Redis health and restore the connection every 30 s."""
    while True:
        await asyncio.sleep(30)
        cache = get_cache_manager()
        if cache and not cache._healthy:
            try:
                await cache.redis.ping()
                cache._healthy = True
                logger.info("Redis connection restored")
            except Exception:
                logger.debug("Redis still unavailable")


async def _invalidate_stats_periodically():
    """Invalidate statistics caches every hour."""
    while True:
        await asyncio.sleep(3600)
        cache = get_cache_manager()
        if cache:
            await cache.invalidate_pattern("stats:*")
            await cache.invalidate_pattern("user_count")
            await cache.invalidate_pattern("admin_count")
            logger.info("Stats cache invalidated by scheduler")


async def _daily_cleanup():
    """Invalidate item/category caches once a day at 03:00."""
    while True:
        now = datetime.now()
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run = next_run.replace(day=next_run.day + 1)
        await asyncio.sleep((next_run - now).total_seconds())
        cache = get_cache_manager()
        if cache:
            await cache.invalidate_pattern("item:*")
            await cache.invalidate_pattern("category:*")
            logger.info("Daily cache cleanup completed")


class CacheScheduler:
    """Scheduler that keeps caches fresh via background asyncio tasks."""

    def __init__(self):
        self.tasks: list[asyncio.Task] = []

    async def start(self):
        """Launch all background cache-maintenance tasks."""
        self.tasks.append(asyncio.create_task(_invalidate_stats_periodically()))
        self.tasks.append(asyncio.create_task(_daily_cleanup()))
        self.tasks.append(asyncio.create_task(_redis_health_monitor()))
        logger.info("Cache scheduler started")

    async def stop(self):
        """Cancel all background tasks and wait for them to finish."""
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("Cache scheduler stopped")
