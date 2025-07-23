import redis.asyncio as redis
import structlog
from config import settings

redis_pool: redis.Redis | None = None
logger = structlog.get_logger(__name__)

async def init_redis_pool():
    global redis_pool
    redis_pool = redis.from_url(
        settings.REDIS_URL, 
        encoding="utf-8", 
        decode_responses=True
    )
    await redis_pool.ping()
    logger.info(
        "Redis connection pool initialized successfully",
        event_type="REDIS_POOL_INITIALIZED",
        trigger_type="system_scheduled",
        redis_url=settings.REDIS_URL,
    )

async def close_redis_pool():
    if redis_pool:
        await redis_pool.close()
        logger.info(
            "Redis connection pool closed successfully",
            event_type="REDIS_POOL_CLOSED",
            trigger_type="system_scheduled",
        )

async def get_redis_client() -> redis.Redis:
    if redis_pool is None:
        raise RuntimeError("Redis connection pool not initialized.")
    return redis_pool