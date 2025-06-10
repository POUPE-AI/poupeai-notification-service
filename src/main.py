from fastapi import FastAPI
from .config import settings
from datetime import datetime

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        debug=settings.debug,
        docs_url="/api/v1/docs",
    )

    @app.get("/api/v1/health")
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.app_name,
            "version": settings.version,
            "timestamp": datetime.now(),
        }

    return app


app = create_app() 