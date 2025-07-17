import asyncio
import aio_pika
import json

from aio_pika.abc import AbstractIncomingMessage
from config import settings

from .exceptions import EventTypeValidationError, SchemaValidationError, TemplateRenderingError, TransientProcessingError
from .gateways import EmailGateway
from .service import EventHandler
from .templating import TemplateManager

class RabbitMQConsumer:
    MAX_RETRIES = settings.RABBITMQ_MAX_RETRIES

    def __init__(self, redis_client):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.redis_client = redis_client
        self._connection = None
        self._channel = None
        self.event_handler = EventHandler(
            redis_client=redis_client,
        )
        print("Consumidor RabbitMQ e EventHandler inicializados com todas as dependências.")

    async def connect(self):
        retry_interval = 5
        while True:
            try:
                print("Tentando conectar ao RabbitMQ...")
                self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self._channel = await self._connection.channel()
                print("Conexão com o RabbitMQ estabelecida com sucesso!")
                break
            except Exception as e:
                print(f"Falha ao conectar: {e}. Tentando novamente em {retry_interval}s...")
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
        print(f"Topologia de Retry com TTL de {retry_delay_ms}ms configurada.")

        self.dlx_exchange = await self._channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_DLQ, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.dlq_queue = await self._channel.declare_queue(
            settings.RABBITMQ_QUEUE_DLQ, durable=True
        )
        await self.dlq_queue.bind(self.dlx_exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)
        print("Topologia de DLQ Final configurada.")

        self.main_exchange = await self._channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_MAIN, aio_pika.ExchangeType.DIRECT, durable=True
        )
        self.main_queue = await self._channel.declare_queue(
            settings.RABBITMQ_QUEUE_MAIN, durable=True
        )
        await self.main_queue.bind(self.main_exchange, routing_key=settings.RABBITMQ_ROUTING_KEY)
        print("Topologia Principal configurada.")

    def _republish_message(self, message: AbstractIncomingMessage) -> aio_pika.Message:
        """
        Cria uma nova mensagem preservando o corpo e as propriedades importantes.
        """
        return aio_pika.Message(
            body=message.body,
            headers=message.headers,
            content_type=message.content_type,
            correlation_id=message.correlation_id,
            delivery_mode=message.delivery_mode
        )

    async def _on_message(self, message: AbstractIncomingMessage):
        correlation_id = message.correlation_id
        retry_count = 0
        if message.headers and "x-death" in message.headers:
            retry_count = message.headers["x-death"][0]["count"]

        print(f"Recebida mensagem. Tentativa #{retry_count + 1}. correlation_id='{correlation_id}'")

        try:
            event_data = json.loads(message.body.decode())
            processed = await self.event_handler.process_event(
                event_data,
                correlation_id,
                retry_count
            )

            if processed:
                print(f"Mensagem processada com sucesso. correlation_id='{correlation_id}'")

            await message.ack()

        except (EventTypeValidationError, SchemaValidationError, json.JSONDecodeError, TemplateRenderingError) as e:
            print(f"[ERRO IRRECUPERÁVEL] {e}. Enviando para DLQ. correlation_id='{correlation_id}'")
            republished_message = self._republish_message(message)
            await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()

        except TransientProcessingError as e:
            print(f"[ERRO TRANSiente] {e}. Tentativa #{retry_count + 1}. correlation_id='{correlation_id}'")
            republished_message = self._republish_message(message)
            if retry_count < self.MAX_RETRIES:
                print("Enviando para a fila de retentativas...")
                await self.retry_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            else:
                print(f"Limite de {self.MAX_RETRIES} tentativas atingido. Enviando para DLQ. correlation_id='{correlation_id}'")
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
            if self._connection:
                await self._connection.close()
                print("Conexão com o RabbitMQ fechada.")