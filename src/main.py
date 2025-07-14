from fastapi import FastAPI
from config import settings
import uvicorn
from notification_service.router import router as notification_router
from notification_service.consumer import RabbitMQConsumer
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer = RabbitMQConsumer()
    consumer_task = asyncio.create_task(consumer.run())
    print("Tarefa do consumidor iniciada em segundo plano.")
    yield
    print("Cancelando a tarefa do consumidor...")
    consumer_task.cancel()
    await consumer_task

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        docs_url="/api/v1/docs",
        lifespan=lifespan,
    )

    app.include_router(
        notification_router,
        prefix="/api/v1",
        tags=["Notification Service"],
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