import asyncio

from pydantic import ValidationError
from pathlib import Path
from typing import Optional

from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors

from config import settings
from .exceptions import EventTypeValidationError, SchemaValidationError, TransientProcessingError, TemplateRenderingError
from .schemas import NotificationEventEnvelope

conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD.get_secret_value() if settings.MAIL_PASSWORD else None,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=settings.MAIL_STARTTLS,
    MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
    TEMPLATE_FOLDER=Path(__file__).parent / 'templates',
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=False
)

class EventHandler:
    def __init__(self, redis_client):
        if not redis_client:
            raise ValueError("O cliente Redis é obrigatório para o EventHandler.")
        self.redis_client = redis_client
        self.event_router = {
            "INVOICE_DUE_SOON": self._handle_invoice_due_soon,
            "INVOICE_OVERDUE": self._handle_invoice_overdue,
            "PROFILE_DELETION_SCHEDULED": self._handle_profile_deletion,
        }

    async def _send_email(self, subject: str, recipient: str, template_name: str, body_context: dict):
        message = MessageSchema(
            subject=subject,
            recipients=[recipient],
            template_body=body_context,
            subtype=MessageType.html
        )
        
        try:
            fm = FastMail(conf)
            await fm.send_message(message, template_name=template_name)
            print(f"E-mail de '{subject}' enviado com sucesso para {recipient}.")
        except ConnectionErrors as e:
            print(f"[EMAIL_ERROR] Falha de conexão ao enviar e-mail: {e}")
            raise TransientProcessingError("Falha de conexão com o servidor de e-mail") from e
        except Exception as e:
            print(f"[EMAIL_ERROR] Erro irrecuperável ao preparar e-mail: {e}")
            raise TemplateRenderingError(f"Falha ao renderizar template {template_name}") from e

    async def _handle_invoice_due_soon(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Processando 'INVOICE_DUE_SOON' para {event.recipient.email}")
        await self._send_email(
            subject="Lembrete Poupe.AI: Sua fatura vence em breve!",
            recipient=event.recipient.email,
            template_name="invoice_due_soon.html",
            body_context=event.model_dump()
        )

    async def _handle_invoice_overdue(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Processando 'INVOICE_OVERDUE' para {event.recipient.email}")
        await self._send_email(
            subject="Aviso de Fatura Vencida - Poupe.AI",
            recipient=event.recipient.email,
            template_name="invoice_overdue.html",
            body_context=event.model_dump()
        )

    async def _handle_profile_deletion(self, event: NotificationEventEnvelope, correlation_id: str, retry_count: int):
        print(f"[HANDLER] Processando 'PROFILE_DELETION_SCHEDULED' para {event.recipient.email}")
        await self._send_email(
            subject="Confirmação de Agendamento de Desativação de Conta Poupe.AI",
            recipient=event.recipient.email,
            template_name="profile_deletion_scheduled.html",
            body_context=event.model_dump()
        )

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