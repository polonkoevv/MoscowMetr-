import redis.asyncio as aioredis
from loguru import logger

from app.config import settings

# Единственный экземпляр клиента на весь процесс
_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    global _redis
    _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=False)
    await _redis.ping()
    logger.info(f"Redis подключён: {settings.REDIS_URL}")


async def close_redis() -> None:
    global _redis
    if _redis:
        await _redis.aclose()
        logger.info("Redis отключён")


def get_redis() -> aioredis.Redis:
    """FastAPI dependency — возвращает готовый клиент."""
    if _redis is None:
        raise RuntimeError("Redis не инициализирован")
    return _redis
