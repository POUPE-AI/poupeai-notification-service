from .schemas import NotificationEventEnvelope
from pydantic import ValidationError
from typing import Optional

class EventHandler:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.event_router = {
            "INVOICE_DUE_SOON": self._handle_invoice_due_soon,
            "INVOICE_OVERDUE": self._handle_invoice_overdue,
            "PROFILE_DEACTIVATION_SCHEDULED": self._handle_profile_deactivation,
        }

    def _handle_invoice_due_soon(self, event: NotificationEventEnvelope, correlation_id: str):
        print(f"[HANDLER] Tratando 'INVOICE_DUE_SOON' para {event.recipient.name}. correlation_id='{correlation_id}'")

    def _handle_invoice_overdue(self, event: NotificationEventEnvelope, correlation_id: str):
        print(f"[HANDLER] Tratando 'INVOICE_OVERDUE' para {event.recipient.name}. correlation_id='{correlation_id}'")

    def _handle_profile_deactivation(self, event: NotificationEventEnvelope, correlation_id: str):
        print(f"[HANDLER] Tratando 'PROFILE_DEACTIVATION_SCHEDULED' para {event.recipient.name}. correlation_id='{correlation_id}'")

    async def process_event(self, event_data: dict, correlation_id: Optional[str] = None):
        try:
            event = NotificationEventEnvelope.model_validate(event_data)
        except ValidationError as e:
            print(f"[VALIDATION_ERROR] Schema inválido. correlation_id='{correlation_id}', error='{e}'")
            return

        print(f"[EVENT_ROUTING] Evento validado. message_id='{event.message_id}', correlation_id='{correlation_id}'")

        message_id = str(event.message_id)
        idempotency_key = f"idempotency:{message_id}"

        was_set = await self.redis_client.set(idempotency_key, 1, nx=True, ex=86400)

        if not was_set:
            print(f"MENSAGEM DUPLICADA DETECTADA. Descartando. message_id='{message_id}'")
            return

        handler = self.event_router.get(event.event_type)
        if handler:
            handler(event, correlation_id)
        else:
            print(f"[HANDLER_NOT_FOUND] Nenhum handler para o event_type '{event.event_type}'. correlation_id='{correlation_id}'")