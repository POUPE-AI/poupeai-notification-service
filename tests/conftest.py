import pytest
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime, UTC
from aio_pika.abc import AbstractIncomingMessage

from config import Settings
from notification_service.service import EmailService


@pytest.fixture
def mock_settings() -> Settings:
    """Fixture to provide a mock Settings object."""
    return MagicMock(spec=Settings)


@pytest.fixture
def mock_redis_client():
    """Mocks the Redis client, using AsyncMock for async methods."""
    mock_client = MagicMock()
    # Default behavior: message does not exist
    mock_client.exists = AsyncMock(return_value=False)
    mock_client.set = AsyncMock()
    mock_client.ping = AsyncMock()  # For health check
    return mock_client


@pytest.fixture
def mock_email_service():
    """Mocks the EmailService."""
    mock_service = MagicMock(spec=EmailService)
    mock_service.send_email = AsyncMock()
    return mock_service


@pytest.fixture
def mock_event_handler():
    """Mocks the EventHandler, used for testing the consumer."""
    mock_handler = MagicMock()
    mock_handler.process_event = AsyncMock()
    return mock_handler


@pytest.fixture
def mock_aio_pika_channel():
    """Mocks the aio_pika channel and its exchanges."""
    mock_channel = MagicMock()
    mock_channel.declare_exchange = AsyncMock()
    mock_channel.declare_queue = AsyncMock(return_value=MagicMock())

    # Mock the exchanges themselves
    mock_retry_exchange = MagicMock()
    mock_retry_exchange.publish = AsyncMock()

    mock_dlx_exchange = MagicMock()
    mock_dlx_exchange.publish = AsyncMock()

    # Make the channel return the correct mock exchange when called
    def exchange_side_effect(name, *args, **kwargs):
        if 'retry' in name:
            return mock_retry_exchange
        if 'dlq' in name:
            return mock_dlx_exchange
        return MagicMock()  # Default for main exchange

    mock_channel.declare_exchange.side_effect = exchange_side_effect

    # Store mocks for easy access in tests
    mock_channel.mock_retry_exchange = mock_retry_exchange
    mock_channel.mock_dlx_exchange = mock_dlx_exchange

    return mock_channel


@pytest.fixture
def event_data_factory():
    """
    A factory fixture that returns a function to generate valid event data.
    This allows overriding specific fields for different test cases.
    """

    def _create_event_data(**overrides):
        """Internal factory function."""

        # Base template for a valid event
        base_event = {
            "message_id": str(uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "trigger_type": "system_scheduled",
            "event_type": "INVOICE_DUE_SOON",
            "recipient": {
                "user_id": "user-123",
                "email": "test.user@example.com",
                "name": "Test User"
            },
            "payload": {
                "credit_card": "Test Card",
                "month": 10,
                "year": 2025,
                "due_date": "2025-10-28",
                "amount": 150.50,
                "invoice_deep_link": "poupeai://app/invoices/1"
            }
        }

        # Apply any overrides provided by the test
        base_event.update(overrides)
        return base_event

    return _create_event_data


@pytest.fixture
def aio_pika_message_factory():
    """A factory fixture to create mock aio_pika messages."""

    def _create_message(
        body: bytes,
        headers: dict | None = None,
        correlation_id: str | None = None
    ) -> AbstractIncomingMessage:
        """Internal factory function."""
        msg = MagicMock(spec=AbstractIncomingMessage)
        msg.body = body
        msg.headers = headers or {}
        msg.correlation_id = correlation_id or str(uuid4())
        msg.ack = AsyncMock()

        # Atribu that _republish_message precisa
        msg.content_type = "application/json"
        msg.delivery_mode = 2  # 2 = Persistent
        msg.routing_key = "test.key"  # Add to log

        # Mock the 'x-death' header structure for retry count
        if 'x-death' not in msg.headers:
            msg.headers['x-death'] = [{}]

        return msg

    return _create_message
