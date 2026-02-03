import asyncio
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict

from fastapi import FastAPI, Depends, Response, status as http_status
from redis.asyncio import Redis
import redis.exceptions
from fastapi_mail import FastMail
from prometheus_fastapi_instrumentator import Instrumentator

from config import settings
from redis_client import init_redis_pool, close_redis_pool, get_redis_client
from notification_service.consumer import RabbitMQConsumer
from notification_service.router import router as notification_router
from notification_service.service import EmailService, EventHandler, get_mail_config

from logging_config import setup_logging
import structlog

app_state: Dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(log_level="DEBUG" if settings.DEBUG else "INFO")

    logger = structlog.get_logger(__name__)
    
    logger.debug("Starting service initialization", event_type="SERVICE_INIT_START")
    
    await init_redis_pool()
    redis_client = await get_redis_client()

    mail_config = get_mail_config(settings)
    email_service = EmailService(FastMail(mail_config))
    event_handler = EventHandler(redis_client=redis_client, email_service=email_service)
    
    consumer = RabbitMQConsumer(event_handler=event_handler)
    
    logger.debug("Starting RabbitMQ consumer task", event_type="CONSUMER_TASK_STARTED")
    consumer_task = asyncio.create_task(consumer.run())
    app_state["consumer_task"] = consumer_task
    
    logger.debug(
        "Application startup complete. Ready to receive requests.",
        event_type="APPLICATION_READY",
        trigger_type="system_scheduled",
    )
    
    yield
    
    logger.debug("Application shutdown initiated", event_type="APPLICATION_SHUTDOWN_START")
    
    consumer_task = app_state.get("consumer_task")
    if consumer_task:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            logger.debug(
                "Consumer task cancelled successfully",
                event_type="CONSUMER_TASK_CANCELLED",
                trigger_type="system_scheduled",
            )
            
    await close_redis_pool()
    
    logger.debug("Application shutdown complete", event_type="APPLICATION_SHUTDOWN_COMPLETE")

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        docs_url="/api/v1/docs",
        lifespan=lifespan,
    )

    Instrumentator().instrument(app).expose(app)

    @app.get(
        "/api/v1/health",
        tags=["Global"],
        summary="Verifica a saúde do serviço e suas dependências",
        responses={
            200: {"description": "Serviço saudável"},
            503: {"description": "Serviço indisponível devido a falha em dependência"},
        },
    )
    async def health_check(response: Response, redis_client: Redis = Depends(get_redis_client)):
        logger = structlog.get_logger(__name__)
        checks = []
        overall_status = "pass"

        try:
            await redis_client.ping()
            checks.append({"component_name": "redis", "status": "pass"})
        except redis.exceptions.ConnectionError as e:
            overall_status = "fail"
            error_output = f"Redis connection error: {e}"
            checks.append({"component_name": "redis", "status": "fail", "output": error_output})
            logger.error(
                "Health check falhou: Erro de conexão com Redis",
                event_type="HEALTH_CHECK_REDIS_FAIL",
                exc_info=e
            )
        except Exception as e:
            overall_status = "fail"
            error_output = f"Health check Redis error: {type(e).__name__} - {e}"
            checks.append({"component_name": "redis", "status": "fail", "output": error_output})
            logger.error(
                "Health check falhou: Erro inesperado",
                event_type="HEALTH_CHECK_UNEXPECTED_FAIL",
                exc_info=e
            )

        health_report = {
            "status": overall_status,
            "service_id": settings.SERVICE_NAME,
            "version": settings.API_VERSION,
            "checks": checks,
        }

        if overall_status == "fail":
            response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

        return health_report

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