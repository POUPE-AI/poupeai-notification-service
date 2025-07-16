import redis.asyncio as redis
from config import settings

redis_client = None

async def init_redis_pool():
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    print("Pool de conexões Redis inicializado.")

async def get_redis_client(): return redis_client

async def close_redis_pool():
    if redis_client: await redis_client.close()