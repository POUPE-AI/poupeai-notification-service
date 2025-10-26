import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi_mail.errors import ConnectionErrors

from notification_service.service import EventHandler, EmailService
from notification_service.exceptions import EventTypeValidationError, TemplateRenderingError, TransientProcessingError
from notification_service.schemas import NotificationEventEnvelope

pytestmark = pytest.mark.asyncio


class TestEventHandler:

    async def test_ut001_idempotency_skips_duplicate_message(
        self, mock_redis_client, mock_email_service, event_data_factory
    ):
        """
        Tests UT-001: Verifies that a message marked as duplicate by Redis
        is skipped and does not trigger an email.
        """
        mock_redis_client.exists.return_value = True  # Mark message as duplicate
        event_data = event_data_factory()

        handler = EventHandler(
            redis_client=mock_redis_client,
            email_service=mock_email_service
        )

        result = await handler.process_event(event_data, correlation_id="test-corr-id-001")

        assert result is False
        mock_redis_client.exists.assert_called_once()
        mock_email_service.send_email.assert_not_called()
        mock_redis_client.set.assert_not_called()

    @pytest.mark.parametrize("event_type, template_name, subject_snippet", [
        ("INVOICE_DUE_SOON", "invoice_due_soon.html", "vence em breve"),
        ("INVOICE_OVERDUE", "invoice_overdue.html", "Fatura Vencida"),
        ("PROFILE_DELETION_SCHEDULED",
         "profile_deletion_scheduled.html", "Desativação de Conta"),
    ])
    async def test_ut005_ut006_ut007_happy_paths(
        self, mock_redis_client, mock_email_service, event_data_factory,
        event_type, template_name, subject_snippet
    ):
        """
        Tests UT-005, UT-006, UT-007: Verifies the happy path for all
        supported event types.
        """
        event_data = event_data_factory(event_type=event_type)
        event_model = NotificationEventEnvelope.model_validate(event_data)

        handler = EventHandler(
            redis_client=mock_redis_client,
            email_service=mock_email_service
        )

        result = await handler.process_event(event_data, correlation_id="test-corr-id-happy")

        assert result is True

        mock_email_service.send_email.assert_called_once()
        call_args = mock_email_service.send_email.call_args

        assert template_name in call_args.kwargs['template_name']
        assert subject_snippet in call_args.kwargs['subject']
        assert event_model.recipient.email == call_args.kwargs['recipient']

        idempotency_key = f"idempotency:{event_model.message_id}"
        mock_redis_client.set.assert_called_once_with(
            idempotency_key, "processed", ex=86400)

    async def test_ut008_unknown_event_type_raises_error(
        self, mock_redis_client, mock_email_service, event_data_factory
    ):
        """
        Tests UT-008: Verifies that an unknown event_type
        raises an EventTypeValidationError.
        """
        event_data = event_data_factory(event_type="UNKNOWN_EVENT")
        handler = EventHandler(
            redis_client=mock_redis_client,
            email_service=mock_email_service
        )

        with pytest.raises(EventTypeValidationError, match="UNKNOWN_EVENT"):
            await handler.process_event(event_data, correlation_id="test-corr-id-008")

        mock_email_service.send_email.assert_not_called()
        mock_redis_client.set.assert_not_called()


class TestEmailService:

    @patch("notification_service.service.MessageSchema")
    async def test_ut003_email_service_raises_transient_on_connection_error(self, mock_message_schema: MagicMock):
        """
        Tests UT-003's cause: Verifies that a ConnectionErrors from fastapi_mail
        is correctly re-raised as a TransientProcessingError.
        """
        mock_mailer = MagicMock()
        mock_mailer.send_message = AsyncMock(
            side_effect=ConnectionErrors("Mock connection failed"))

        email_service = EmailService(mailer=mock_mailer)

        with pytest.raises(TransientProcessingError, match="Failed to connect"):
            await email_service.send_email(
                subject="test",
                recipient="test@test.com",
                template_name="test.html",
                body_context={}
            )

    @patch("notification_service.service.MessageSchema")
    async def test_ut011_email_service_raises_template_error_on_render_failure(self, mock_message_schema: MagicMock):
        """
        Tests UT-011's cause: Verifies that a generic exception during sending
        (like a template render error) is re-raised as TemplateRenderingError.
        """
        mock_mailer = MagicMock()
        mock_mailer.send_message = AsyncMock(
            side_effect=Exception("Mock render failed"))

        email_service = EmailService(mailer=mock_mailer)

        with pytest.raises(TemplateRenderingError, match="Failed to render"):
            await email_service.send_email(
                subject="test",
                recipient="test@test.com",
                template_name="test.html",
                body_context={}
            )
