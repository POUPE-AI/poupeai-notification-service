from fastapi import APIRouter

router = APIRouter()

@router.get("/status")
async def get_notification_status():
    """
    Endpoint de exemplo para o status do módulo de notificação.
    """
    return {"module": "notification-service", "status": "ok"}