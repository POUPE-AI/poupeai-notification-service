from fastapi import FastAPI
from config import settings
import uvicorn
from notification_service.router import router as notification_router

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.API_VERSION,
        debug=settings.DEBUG,
        docs_url="/api/v1/docs",
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