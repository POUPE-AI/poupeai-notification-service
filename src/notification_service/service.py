from pathlib import Path
import structlog
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

logger = structlog.get_logger(__name__)


class EmailService:
    def __init__(self, mailer: FastMail):
        self.mailer = mailer

    async def send_email(self, subject: str, recipient: str, template_name: str, body_context: dict, correlation_id: Optional[str] = None):
        log = logger.bind(correlation_id=correlation_id,
                          recipient=recipient, subject=subject, template=template_name)

        message = MessageSchema(
            subject=subject,
            recipients=[recipient],
            template_body=body_context,
            subtype=MessageType.html
        )
        try:
            log.info("Starting email delivery",
                     event_type="EMAIL_DELIVERY_START")
            await self.mailer.send_message(message, template_name=template_name)
            log.info("Email sent successfully",
                     event_type="EMAIL_SENT_SUCCESSFULLY")
        except ConnectionErrors as e:
            log.error(
                "Failed to connect to email server",
                event_type="EMAIL_SEND_FAILED_CONNECTION",
                error=str(e),
                exc_info=e
            )
            raise TransientProcessingError(
                f"Failed to connect to the email server: {e}") from e
        except Exception as e:
            log.error(
                "Failed to render email template",
                event_type="EMAIL_SEND_FAILED_RENDER",
                error=str(e),
                exc_info=e
            )
            raise TemplateRenderingError(
                f"Failed to render template {template_name}: {e}") from e


class EventHandler:
    def __init__(self, redis_client: Redis, email_service: EmailService):
        self.redis_client = redis_client
        self.email_service = email_service
        self.event_router = {
            "INVOICE_DUE_SOON": self._handle_invoice_due_soon,
            "INVOICE_OVERDUE": self._handle_invoice_overdue,
            "PROFILE_DELETION_SCHEDULED": self._handle_profile_deletion,
        }

    async def _handle_invoice_due_soon(self, event: NotificationEventEnvelope, correlation_id: str, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Lembrete: Sua fatura vence em breve!",
            recipient=event.recipient.email,
            template_name="invoice_due_soon.html",
            body_context=event.model_dump(),
            correlation_id=correlation_id
        )

    async def _handle_invoice_overdue(self, event: NotificationEventEnvelope, correlation_id: str, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Aviso de Fatura Vencida",
            recipient=event.recipient.email,
            template_name="invoice_overdue.html",
            body_context=event.model_dump(),
            correlation_id=correlation_id
        )

    async def _handle_profile_deletion(self, event: NotificationEventEnvelope, correlation_id: str, **_):
        await self.email_service.send_email(
            subject="Poupe.AI - Confirmação de Agendamento de Desativação de Conta",
            recipient=event.recipient.email,
            template_name="profile_deletion_scheduled.html",
            body_context=event.model_dump(),
            correlation_id=correlation_id
        )

    async def process_event(self, event_data: dict, correlation_id: Optional[str] = None, retry_count: int = 0) -> bool:
        log = logger.bind(correlation_id=correlation_id, event_type=event_data.get(
            "event_type", "unknown"), retry_count=retry_count)

        try:
            event = NotificationEventEnvelope.model_validate(event_data)
        except ValidationError as e:
            raise SchemaValidationError(f"Invalid message schema: {e}")

        idempotency_key = f"idempotency:{event.message_id}"

        # ---------------------------------------------------------
        # [MUTANTE M1] - Operador Lógico (Negação de Condição)
        # Objetivo: Testar se a suíte detecta falha na verificação de duplicidade.
        # Teste Alvo: test_ut001_idempotency_skips_duplicate_message
        # ---------------------------------------------------------
        
        # [CÓDIGO ORIGINAL]
        if await self.redis_client.exists(idempotency_key):
        
        # [CÓDIGO MUTADO - Descomente abaixo e comente o original para ativar]
        # if not await self.redis_client.exists(idempotency_key): 
            log.warning(
                "Duplicate message detected via idempotency check. Skipping.",
                event_type="MESSAGE_IDEMPOTENCY_DUPLICATE",
                event_details={"message_id": event.message_id}
            )
            return False

        handler = self.event_router.get(event.event_type)
        if not handler:
            raise EventTypeValidationError(event.event_type)

        log.info(
            "Processing event with handler",
            event_type="EVENT_PROCESSING_START",
            event_details={"handler_name": handler.__name__,
                           "recipient_email": event.recipient.email}
        )

        await handler(event=event, correlation_id=correlation_id, retry_count=retry_count)

        # ---------------------------------------------------------
        # [MUTANTE M2] - Alteração de Constante (TTL)
        # Objetivo: Testar se a suíte valida os parâmetros exatos de persistência.
        # Teste Alvo: test_ut005_ut006_ut007_happy_paths
        # ---------------------------------------------------------

        # [CÓDIGO ORIGINAL]
        await self.redis_client.set(idempotency_key, "processed", ex=86400)

        # [CÓDIGO MUTADO - Descomente abaixo e comente o original para ativar]
        # await self.redis_client.set(idempotency_key, "processed", ex=10) 
        
        log.info(
            "Message marked as processed in Redis via idempotency key.",
            event_type="MESSAGE_IDEMPOTENCY_PROCESSED",
            event_details={"message_id": event.message_id,
                           "ttl_seconds": 86400}
        )
        return True


def get_mail_config(settings: Settings = Depends(lambda: app_settings)) -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD.get_secret_value(
        ) if settings.MAIL_PASSWORD else None,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.MAIL_PORT,
        MAIL_SERVER=settings.MAIL_SERVER,
        MAIL_STARTTLS=settings.MAIL_STARTTLS,
        MAIL_SSL_TLS=settings.MAIL_SSL_TLS,
        TEMPLATE_FOLDER=Path(__file__).parent / 'templates',
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=False,
        SUPPRESS_SEND=settings.MAIL_SUPPRESS_SEND
    )


def get_email_service(mail_config: ConnectionConfig = Depends(get_mail_config)) -> EmailService:
    mailer = FastMail(mail_config)
    return EmailService(mailer)


def get_event_handler(
    redis_client: Redis = Depends(get_redis_client),
    email_service: EmailService = Depends(get_email_service)
) -> EventHandler:
    return EventHandler(redis_client=redis_client, email_service=email_service)
