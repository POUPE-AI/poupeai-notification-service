from pathlib import Path
from typing import Optional

from fastapi import Depends
from pydantic import ValidationError
from redis.asyncio import Redis
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from fastapi_mail.errors import ConnectionErrors

from config import Settings, settings as app_settings
from redis_client import get_redis_client
from .exceptions import EventTypeValidationError, SchemaValidationError, TransientProcessingError, TemplateRenderingError
from .schemas import NotificationEventEnvelope

class EmailService:
    def __init__(self, mailer: FastMail):
        self.mailer = mailer

    async def send_email(self, subject: str, recipient: str, template_name: str, body_context: dict):
        message = MessageSchema(
            subject=subject,
            recipients=[recipient],
            template_body=body_context,
            subtype=MessageType.html
        )
        try:
            await self.mailer.send_message(message, template_name=template_name)
            print(f"E-mail de '{subject}' enviado com sucesso para {recipient}.")
        except ConnectionErrors as e:
            raise TransientProcessingError(f"Falha de conexão com o servidor de e-mail: {e}") from e
        except Exception as e:
            raise TemplateRenderingError(f"Falha ao renderizar o template {template_name}: {e}") from e

class EventHandler:
    def __init__(self, redis_client: Redis, email_service: EmailService):
        self.redis_client = redis_client
        self.email_service = email_service
        self.event_router = {
            "INVOICE_DUE_SOON": self._handle_invoice_due_soon,
            "INVOICE_OVERDUE": self._handle_invoice_overdue,
            "PROFILE_DELETION_SCHEDULED": self._handle_profile_deletion,
        }

    async def _handle_invoice_due_soon(self, event: NotificationEventEnvelope, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Lembrete: Sua fatura vence em breve!",
            recipient=event.recipient.email,
            template_name="invoice_due_soon.html",
            body_context=event.model_dump()
        )

    async def _handle_invoice_overdue(self, event: NotificationEventEnvelope, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Aviso de Fatura Vencida",
            recipient=event.recipient.email,
            template_name="invoice_overdue.html",
            body_context=event.model_dump()
        )

    async def _handle_profile_deletion(self, event: NotificationEventEnvelope, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Confirmação de Agendamento de Desativação de Conta",
            recipient=event.recipient.email,
            template_name="profile_deletion_scheduled.html",
            body_context=event.model_dump()
        )

    async def process_event(self, event_data: dict, correlation_id: Optional[str] = None, retry_count: int = 0) -> bool:
        try:
            event = NotificationEventEnvelope.model_validate(event_data)
        except ValidationError as e:
            raise SchemaValidationError(f"Schema da mensagem inválido: {e}")

        idempotency_key = f"idempotency:{event.message_id}"
        if await self.redis_client.exists(idempotency_key):
            print(f"[IDEMPOTENCY_CHECK] Mensagem duplicada ignorada. message_id='{event.message_id}'")
            return False

        handler = self.event_router.get(event.event_type)
        if not handler:
            raise EventTypeValidationError(event.event_type)

        print(f"[HANDLER] Processando '{event.event_type}' para {event.recipient.email}")
        await handler(event=event, correlation_id=correlation_id, retry_count=retry_count)

        await self.redis_client.set(idempotency_key, "processed", ex=86400)
        print(f"[IDEMPOTENCY_CHECK] Mensagem marcada como processada. message_id='{event.message_id}'")
        return True

def get_mail_config(settings: Settings = Depends(lambda: app_settings)) -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD.get_secret_value() if settings.MAIL_PASSWORD else None,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        TEMPLATE_FOLDER=Path(__file__).parent / 'templates',
    )

def get_email_service(mail_config: ConnectionConfig = Depends(get_mail_config)) -> EmailService:
    mailer = FastMail(mail_config)
    return EmailService(mailer)

def get_event_handler(
    redis_client: Redis = Depends(get_redis_client),
    email_service: EmailService = Depends(get_email_service)
) -> EventHandler:
    return EventHandler(redis_client=redis_client, email_service=email_service)