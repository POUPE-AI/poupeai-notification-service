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
        print("Consumidor RabbitMQ inicializado.")

    async def connect(self):
        retry_interval = 5
        while True:
            try:
                print("Tentando conectar ao RabbitMQ...")
                self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self._channel = await self._connection.channel()
                print("Conexão com o RabbitMQ estabelecida com sucesso!")
                return
            except Exception as e:
                print(f"Falha ao conectar ao RabbitMQ: {e}. Tentando novamente em {retry_interval}s...")
                await asyncio.sleep(retry_interval)

    async def _setup_queues(self):
        if not self._channel:
            raise ConnectionError("Canal de comunicação não disponível.")

        print("Configurando a topologia do RabbitMQ...")

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
        print("Topologia do RabbitMQ configurada.")

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

        log = logger.bind(
            correlation_id=correlation_id,
            message_id=message.message_id,
            delivery_tag=message.delivery_tag
        )

        retry_count = message.headers.get("x-death", [{}])[0].get("count", 0)

        log.info(
            "message_received",
            retry_count=retry_count,
            exchange=message.exchange,
            routing_key=message.routing_key
        )

        try:
            event_data = json.loads(message.body.decode())
            processed = await self.event_handler.process_event(
                event_data, correlation_id, retry_count
            )
            await message.ack()
            log.info("message_processed_and_acked")

        except (EventTypeValidationError, SchemaValidationError, json.JSONDecodeError, TemplateRenderingError) as e:
            log.error("unrecoverable_error_sending_to_dlq", reason=str(e))
            republished_message = self._republish_message(message)
            await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()

        except TransientProcessingError as e:
            log.warn("transient_error_handling", reason=str(e), retry_count=retry_count)
            republished_message = self._republish_message(message)
            if retry_count < self.MAX_RETRIES:
                log.info("message_republishing_to_retry_queue")
                await self.retry_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            else:
                log.error("max_retries_reached_sending_to_dlq", max_retries=self.MAX_RETRIES)
                await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()

    async def run(self):
        await self.connect()
        await self._setup_queues()
        print("Consumidor pronto e aguardando por mensagens...")
        await self.main_queue.consume(self._on_message)
        try:
            await asyncio.Future()
        finally:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
                print("Conexão com o RabbitMQ fechada.")