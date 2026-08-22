# bot/cache/__init__.py
from apps.telegram_bot.cache.manager import CacheManager, cache_result, get_cache_manager, init_cache_manager
from apps.telegram_bot.cache.scheduler import CacheScheduler
from apps.telegram_bot.cache.storage import get_redis_storage
from apps.telegram_bot.cache.stats import StatsCache

__all__ = [
    "CacheManager",
    "cache_result",
    "get_cache_manager",
    "init_cache_manager",
    "CacheScheduler",
    "get_redis_storage",
    "StatsCache",
]
