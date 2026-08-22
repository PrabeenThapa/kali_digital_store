import logging
from typing import Optional, Literal

from redis.asyncio import Redis
from aiogram.fsm.storage.redis import RedisStorage, StorageKey

from packages.config.config import EnvKeys


class CustomRedisStorage(RedisStorage):
    """
    Redis FSM storage with configurable TTL on state and data keys.
    Prevents unbounded key accumulation for abandoned sessions.
    """

    def __init__(
        self,
        redis: Redis,
        state_ttl: Optional[int] = 3600,  # 1 hour by default
        data_ttl: Optional[int] = 3600,
    ):
        super().__init__(redis=redis)
        self.state_ttl = state_ttl
        self.data_ttl = data_ttl

    async def set_state(self, key: StorageKey, state: str = None) -> None:
        """Set FSM state with TTL."""
        await super().set_state(key, state)
        if state and self.state_ttl:
            redis_key = self._build_key(key, "state")
            await self.redis.expire(redis_key, self.state_ttl)

    async def set_data(self, key: StorageKey, data: dict) -> None:
        """Set FSM data with TTL."""
        await super().set_data(key, data)
        if data and self.data_ttl:
            redis_key = self._build_key(key, "data")
            await self.redis.expire(redis_key, self.data_ttl)

    def _build_key(self, key: StorageKey, part: Literal["data", "state", "lock"]) -> str:
        """Build the full Redis key string."""
        assert self.key_builder is not None, "KeyBuilder should be initialized"
        return self.key_builder.build(key, part)


def get_redis_storage() -> Optional[RedisStorage]:
    """
    Build and return a RedisStorage instance.
    Returns None if Redis is disabled or unavailable.
    """
    if EnvKeys.REDIS_ENABLED != "1":
        logging.info("Redis is disabled via REDIS_ENABLED=0")
        return None

    try:
        redis = Redis(
            host=EnvKeys.REDIS_HOST,
            port=EnvKeys.REDIS_PORT,
            db=EnvKeys.REDIS_DB,
            password=EnvKeys.REDIS_PASSWORD,
            decode_responses=False,
            socket_connect_timeout=5,
            socket_timeout=5,
        )
        storage = CustomRedisStorage(redis=redis, state_ttl=3600, data_ttl=3600)
        logging.info(f"Redis storage configured: {EnvKeys.REDIS_HOST}:{EnvKeys.REDIS_PORT}")
        return storage
    except Exception as e:
        logging.error(f"Failed to create Redis storage: {e}")
        return None
