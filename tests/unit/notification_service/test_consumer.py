import pytest
import json
from unittest.mock import MagicMock, AsyncMock
from notification_service.consumer import RabbitMQConsumer, settings
from notification_service.exceptions import EventTypeValidationError, SchemaValidationError, TransientProcessingError

pytestmark = pytest.mark.asyncio


@pytest.fixture
def consumer_instance(mock_event_handler, mock_aio_pika_channel):
    """Fixture to create a pre-configured RabbitMQConsumer instance."""

    # Mock settings used by the consumer
    settings.RABBITMQ_MAX_RETRIES = 3
    settings.RABBITMQ_EXCHANGE_RETRY = "test.retry"
    settings.RABBITMQ_EXCHANGE_DLQ = "test.dlq"
    settings.RABBITMQ_ROUTING_KEY = "test.key"

    consumer = RabbitMQConsumer(event_handler=mock_event_handler)

    # Inject mock channel and exchanges
    consumer._channel = mock_aio_pika_channel
    consumer.retry_exchange = mock_aio_pika_channel.mock_retry_exchange
    consumer.dlx_exchange = mock_aio_pika_channel.mock_dlx_exchange

    # 'main_queue' that is used in logs
    consumer.main_queue = MagicMock(name="mock_main_queue")
    consumer.main_queue.name = "mock_main_queue_name"

    return consumer


class TestRabbitMQConsumer:

    async def test_ut011_happy_path_acks_message(
        self, consumer_instance, aio_pika_message_factory, event_data_factory
    ):
        """
        Tests UT-011: Verifies that a message processed successfully (Happy Path)
        is acknowledged.
        
        This test kills Mutant 05 (Omission of ack in success flow).
        """
        consumer_instance.event_handler.process_event.return_value = True
        
        event_data = event_data_factory()
        message = aio_pika_message_factory(
            body=json.dumps(event_data).encode('utf-8')
        )

        await consumer_instance._on_message(message)

        consumer_instance.event_handler.process_event.assert_awaited_once()
        message.ack.assert_awaited_once()
        
        consumer_instance.retry_exchange.publish.assert_not_called()
        consumer_instance.dlx_exchange.publish.assert_not_called()

    async def test_ut003_transient_error_schedules_retry(
        self, consumer_instance, aio_pika_message_factory, event_data_factory
    ):
        """
        Tests UT-003: Verifies that a TransientProcessingError
        routes the message to the retry exchange.
        """
        consumer_instance.event_handler.process_event.side_effect = TransientProcessingError(
            "Mock transient error")

        event_data = event_data_factory()
        message = aio_pika_message_factory(
            body=json.dumps(event_data).encode('utf-8'))

        await consumer_instance._on_message(message)

        consumer_instance.retry_exchange.publish.assert_called_once()
        consumer_instance.dlx_exchange.publish.assert_not_called()
        message.ack.assert_called_once()

    @pytest.mark.parametrize("error", [
        (SchemaValidationError("Mock schema error")),
        (EventTypeValidationError("Mock event type error")),
    ])
    async def test_ut004_unrecoverable_error_sends_to_dlq(
        self, consumer_instance, aio_pika_message_factory, event_data_factory, error
    ):
        """
        Tests UT-004: Verifies that unrecoverable errors
        (Schema, EventType) route the message to the DLQ.
        """
        consumer_instance.event_handler.process_event.side_effect = error

        event_data = event_data_factory()
        message = aio_pika_message_factory(
            body=json.dumps(event_data).encode('utf-8'))

        await consumer_instance._on_message(message)

        consumer_instance.dlx_exchange.publish.assert_called_once()
        consumer_instance.retry_exchange.publish.assert_not_called()
        message.ack.assert_called_once()

    async def test_ut009_invalid_json_sends_to_dlq(
        self, consumer_instance, aio_pika_message_factory
    ):
        """
        Tests UT-009: Verifies that a message with invalid JSON
        is routed directly to the DLQ.
        """
        invalid_body = b'{"invalid_json": "missing_quote}'
        message = aio_pika_message_factory(body=invalid_body)

        await consumer_instance._on_message(message)

        consumer_instance.dlx_exchange.publish.assert_called_once()
        consumer_instance.retry_exchange.publish.assert_not_called()
        consumer_instance.event_handler.process_event.assert_not_called()
        message.ack.assert_called_once()

    async def test_ut010_max_retries_sends_to_dlq(
        self, consumer_instance, aio_pika_message_factory, event_data_factory
    ):
        """
        Tests UT-010: Verifies that a message that fails with a
        transient error but has reached max retries is sent to the DLQ.
        """
        consumer_instance.event_handler.process_event.side_effect = TransientProcessingError(
            "Mock transient error")

        headers = {
            "x-death": [
                {"count": settings.RABBITMQ_MAX_RETRIES}
            ]
        }
        event_data = event_data_factory()
        message = aio_pika_message_factory(
            body=json.dumps(event_data).encode('utf-8'),
            headers=headers
        )

        await consumer_instance._on_message(message)

        consumer_instance.dlx_exchange.publish.assert_called_once()
        consumer_instance.retry_exchange.publish.assert_not_called()
        message.ack.assert_called_once()
