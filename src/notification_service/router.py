from fastapi import APIRouter
from datetime import datetime
from config import settings

router = APIRouter()

@router.get("/health")
async def health_check():
    """
    Endpoint para verificar a saúde do serviço.
    """
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.API_VERSION,
        "timestamp": datetime.now(),
    }