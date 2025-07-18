import asyncio
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Depends
from redis.asyncio import Redis
from fastapi_mail import FastMail

from config import settings
from redis_client import init_redis_pool, close_redis_pool, get_redis_client
from notification_service.consumer import RabbitMQConsumer
from notification_service.router import router as notification_router
from notification_service.service import EmailService, EventHandler, get_mail_config

app_state: Dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_redis_pool()
    redis_client = await get_redis_client()

    mail_config = get_mail_config(settings)
    email_service = EmailService(FastMail(mail_config))
    event_handler = EventHandler(redis_client=redis_client, email_service=email_service)
    
    consumer = RabbitMQConsumer(event_handler=event_handler)
    
    consumer_task = asyncio.create_task(consumer.run())
    app_state["consumer_task"] = consumer_task
    
    print("Startup concluído. A aplicação está pronta para receber requisições.")
    
    yield
    
    print("Executando tarefas de shutdown...")
    
    consumer_task = app_state.get("consumer_task")
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            print("Tarefa do consumidor cancelada com sucesso.")
            
    await close_redis_pool()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        docs_url="/api/v1/docs",
        lifespan=lifespan,
    )

    @app.get("/api/v1/health", tags=["Global"])
    async def health_check(redis: Redis = Depends(get_redis_client)):
        await redis.ping()
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "redis_connection": "ok"
        }

    app.include_router(
        notification_router,
        prefix="/api/v1/notifications",
        tags=["Notifications"],
    )

    return app

app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )