import redis.asyncio as redis
from config import settings

redis_pool: redis.Redis | None = None

async def init_redis_pool():
    global redis_pool
    redis_pool = redis.from_url(
        settings.REDIS_URL, 
        encoding="utf-8", 
        decode_responses=True
    )
    await redis_pool.ping()
    print("Pool de conexões Redis inicializado e verificado com sucesso.")

async def close_redis_pool():
    if redis_pool:
        await redis_pool.close()
        print("Pool de conexões Redis fechado.")

async def get_redis_client() -> redis.Redis:
    if redis_pool is None:
        raise RuntimeError("O pool de conexões Redis não foi inicializado.")
    return redis_pool