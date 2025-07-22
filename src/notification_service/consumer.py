import asyncio
import aio_pika
import json
import structlog
from uuid import uuid4

from aio_pika.abc import AbstractIncomingMessage
from config import settings
from .exceptions import EventTypeValidationError, SchemaValidationError, TemplateRenderingError, TransientProcessingError
from .service import EventHandler

logger = structlog.get_logger(__name__)

class RabbitMQConsumer:
    MAX_RETRIES = settings.RABBITMQ_MAX_RETRIES

    def __init__(self, event_handler: EventHandler):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.event_handler = event_handler
        self._connection = None
        self._channel = None
        logger.info("rabbitmq_consumer_initialized")

    async def connect(self):
        retry_interval = 5
        while True:
            try:
                logger.info("rabbitmq_connecting")
                self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self._channel = await self._connection.channel()
                logger.info("rabbitmq_connected_successfully")
                return
            except Exception as e:
                logger.error("rabbitmq_connection_failed", error=str(e), retry_in_seconds=retry_interval)
                await asyncio.sleep(retry_interval)

    async def _setup_queues(self):
        if not self._channel:
            raise ConnectionError("Canal de comunicação não disponível.")

        logger.info("rabbitmq_topology_setup_starting")
        
        retry_exchange_name = settings.RABBITMQ_EXCHANGE_RETRY
        retry_queue_name = settings.RABBITMQ_QUEUE_RETRY
        retry_delay_ms = settings.RABBITMQ_RETRY_DELAY_MS

        self.retry_exchange = await self._channel.declare_exchange(
            retry_exchange_name, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.retry_queue = await self._channel.declare_queue(
            retry_queue_name,
            durable=True,
            arguments={
                "x-message-ttl": retry_delay_ms,
                "x-dead-letter-exchange": settings.RABBITMQ_EXCHANGE_MAIN,
                "x-dead-letter-routing-key": settings.RABBITMQ_ROUTING_KEY,
            },
        )
        await self.retry_queue.bind(self.retry_exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)

        self.dlx_exchange = await self._channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_DLQ, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.dlq_queue = await self._channel.declare_queue(
            settings.RABBITMQ_QUEUE_DLQ, durable=True
        )
        await self.dlq_queue.bind(self.dlx_exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)

        self.main_exchange = await self._channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_MAIN, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.main_queue = await self._channel.declare_queue(
            settings.RABBITMQ_QUEUE_MAIN, durable=True
        )
        await self.main_queue.bind(self.main_exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)
        logger.info("rabbitmq_topology_setup_finished")

    def _republish_message(self, message: AbstractIncomingMessage) -> aio_pika.Message:
        return aio_pika.Message(
            body=message.body,
            headers=message.headers,
            content_type=message.content_type,
            correlation_id=message.correlation_id,
            delivery_mode=message.delivery_mode
        )

    async def _on_message(self, message: AbstractIncomingMessage):
        correlation_id = message.correlation_id or str(uuid4())
        log = logger.bind(correlation_id=correlation_id)
        event_data = {}

        try:
            event_data = json.loads(message.body.decode())
            retry_count = message.headers.get("x-death", [{}])[0].get("count", 0)

            log.info(
                f"Message received on queue '{self.main_queue.name}'.",
                event_type="MESSAGE_RECEIVED",
                trigger_type=event_data.get("trigger_type"),
                actor_user_id=event_data.get("recipient", {}).get("user_id"),
                rabbitmq_details={"retry_count": retry_count, "routing_key": message.routing_key}
            )

            await self.event_handler.process_event(event_data, correlation_id)
            await message.ack()

        except (EventTypeValidationError, SchemaValidationError, json.JSONDecodeError, TemplateRenderingError) as e:
            log.error(
                f"Unrecoverable error: {e}. Moving message to DLQ.",
                event_type="MESSAGE_SENT_TO_DLQ",
                reason=str(e),
                trigger_type=event_data.get("trigger_type", "unknown"),
                actor_user_id=event_data.get("recipient", {}).get("user_id"),
            )
            republished_message = self._republish_message(message)
            await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()

        except TransientProcessingError as e:
            retry_count = message.headers.get("x-death", [{}])[0].get("count", 0)
            log_details = {
                "trigger_type": event_data.get("trigger_type"),
                "actor_user_id": event_data.get("recipient", {}).get("user_id")
            }
            if retry_count < self.MAX_RETRIES:
                log.info(
                    f"Transient error: {e}. Scheduling retry.",
                    event_type="MESSAGE_RETRY_SCHEDULED",
                    retry_details={"current_attempt": retry_count + 1, "max_retries": self.MAX_RETRIES},
                    **log_details
                )
                republished_message = self._republish_message(message)
                await self.retry_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            else:
                log.error(
                    f"Max retries ({self.MAX_RETRIES}) reached. Moving message to DLQ.",
                    event_type="MESSAGE_SENT_TO_DLQ_MAX_RETRIES",
                    last_error=str(e),
                    **log_details
                )
                republished_message = self._republish_message(message)
                await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()
    
    async def run(self):
        await self.connect()
        await self._setup_queues()
        logger.info("consumer_ready_and_waiting")
        await self.main_queue.consume(self._on_message)
        try:
            await asyncio.Future()
        finally:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
                logger.info("rabbitmq_connection_closed")