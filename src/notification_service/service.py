import asyncio

from pydantic import ValidationError
from typing import Optional

from .exceptions import EventTypeValidationError, SchemaValidationError, TemplateRenderingError, TransientProcessingError
from .gateways import EmailGateway
from .schemas import NotificationEventEnvelope
from .templating import TemplateManager

class EventHandler:
    def __init__(self, redis_client, email_gateway: EmailGateway, template_manager: TemplateManager):
        if not redis_client:
            raise ValueError("O cliente Redis é obrigatório para o EventHandler.")
        if not email_gateway:
            raise ValueError("O EmailGateway é obrigatório para o EventHandler.")
        if not template_manager:
            raise ValueError("O TemplateManager é obrigatório para o EventHandler.")
            
        self.redis_client = redis_client
        self.email_gateway = email_gateway
        self.template_manager = template_manager

        self.event_router = {
            "INVOICE_DUE_SOON": self._handle_invoice_due_soon,
            "INVOICE_OVERDUE": self._handle_invoice_overdue,
            "PROFILE_DEACTIVATION_SCHEDULED": self._handle_profile_deactivation,
        }

    async def _handle_invoice_due_soon(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Iniciando envio de 'INVOICE_DUE_SOON' para {event.recipient.email} (correlation_id: {correlation_id})")
        
        subject = f"Lembrete Poupe.AI: Sua fatura vence em breve!"
        template_name = "invoice_due_soon.html"

        html_content = self.template_manager.render(template_name, event.model_dump())
        
        await self.email_gateway.send(
            to_email=event.recipient.email,
            subject=subject,
            html_content=html_content
        )
        print(f"[HANDLER] E-mail 'INVOICE_DUE_SOON' enviado com sucesso para {event.recipient.email}.")

    async def _handle_invoice_overdue(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Iniciando envio de 'INVOICE_OVERDUE' para {event.recipient.email} (correlation_id: {correlation_id})")
        
        subject = f"Aviso de Fatura Vencida - Poupe.AI"
        template_name = "invoice_overdue.html"

        html_content = self.template_manager.render(template_name, event.model_dump())
        
        await self.email_gateway.send(
            to_email=event.recipient.email,
            subject=subject,
            html_content=html_content
        )
        print(f"[HANDLER] E-mail 'INVOICE_OVERDUE' enviado com sucesso para {event.recipient.email}.")

    async def _handle_profile_deactivation(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Iniciando envio de 'PROFILE_DEACTIVATION_SCHEDULED' para {event.recipient.email} (correlation_id: {correlation_id})")

        subject = "Confirmação de Agendamento de Desativação de Conta Poupe.AI"
        template_name = "profile_deactivation_scheduled.html"

        html_content = self.template_manager.render(template_name, event.model_dump())
        
        await self.email_gateway.send(
            to_email=event.recipient.email,
            subject=subject,
            html_content=html_content
        )
        print(f"[HANDLER] E-mail 'PROFILE_DEACTIVATION_SCHEDULED' enviado com sucesso para {event.recipient.email}.")

    async def process_event(self, event_data: dict, correlation_id: Optional[str] = None, retry_count: int = 0) -> bool:
        try:
            event = NotificationEventEnvelope.model_validate(event_data)
        except ValidationError as e:
            raise SchemaValidationError(f"Schema inválido: {e}")

        message_id = str(event.message_id)
        idempotency_key = f"idempotency:{message_id}"

        if await self.redis_client.exists(idempotency_key):
            print(f"[IDEMPOTENCY_CHECK] MENSAGEM DUPLICADA de um sucesso anterior. Descartando. message_id='{message_id}', correlation_id='{correlation_id}'")
            return False

        print(f"[EVENT_ROUTING] Evento novo. Tentando processar. message_id='{message_id}', correlation_id='{correlation_id}'")

        handler = self.event_router.get(event.event_type)
        if not handler:
            raise EventTypeValidationError(event.event_type, "Handler não encontrado para o tipo de evento")

        await handler(event, correlation_id, retry_count)

        await self.redis_client.set(idempotency_key, "processed", ex=86400)
        print(f"[IDEMPOTENCY_CHECK] Mensagem marcada como processada no Redis. message_id='{message_id}'")

        return True