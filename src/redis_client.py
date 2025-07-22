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
    logger.info("redis_pool_initialized_successfully")

async def close_redis_pool():
    if redis_pool:
        await redis_pool.close()
        logger.info("redis_pool_closed")

async def get_redis_client() -> redis.Redis:
    if redis_pool is None:
        raise RuntimeError("O pool de conexões Redis não foi inicializado.")
    return redis_pool