import asyncio
import aio_pika
from aio_pika.abc import AbstractIncomingMessage
from config import settings
import json
from .service import EventHandler

class RabbitMQConsumer:
    def __init__(self):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self._connection = None
        self._channel = None
        self.event_handler = EventHandler()
        print("Consumidor RabbitMQ e EventHandler inicializados.")

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

        self.dlx_exchange = await self._channel.declare_exchange(
            "notification_exchange.dlq", aio_pika.ExchangeType.DIRECT, durable=True
        )
        print("Exchange DLQ 'notification_exchange.dlq' declarada.")

        self.dlq_queue = await self._channel.declare_queue(
            "notification_events.dlq", durable=True
        )
        print("Fila DLQ 'notification_events.dlq' declarada.")

        await self.dlq_queue.bind(self.dlx_exchange, routing_key="notification.event")
        print("Bind entre DLQ e DLX realizado.")

        self.main_exchange = await self._channel.declare_exchange(
            "notification_exchange", aio_pika.ExchangeType.DIRECT, durable=True
        )
        print("Exchange principal 'notification_exchange' declarada.")
        
        self.main_queue = await self._channel.declare_queue(
            "notification_events",
            durable=True,
            arguments={
                "x-dead-letter-exchange": "notification_exchange.dlq",
                "x-dead-letter-routing-key": "notification.event",
            },
        )
        print("Fila principal 'notification_events' com argumentos DLQ declarada.")

        await self.main_queue.bind(self.main_exchange, routing_key="notification.event")
        print("Bind entre Fila principal e Exchange principal realizado.")
        print("Topologia do RabbitMQ configurada com sucesso.")


    async def _on_message(self, message: AbstractIncomingMessage):
        async with message.process(ignore_processed=True):
            body = message.body.decode()
            correlation_id = message.correlation_id

            try:
                event_data = json.loads(body)
                await self.event_handler.process_event(
                    event_data=event_data, 
                    correlation_id=correlation_id
                )
            except json.JSONDecodeError:
                print(f"[DECODE_ERROR] Corpo da mensagem não é JSON. correlation_id='{correlation_id}'. Descartando.")
            except Exception as e:
                print(f"[UNEXPECTED_ERROR] Erro no processamento. correlation_id='{correlation_id}', error='{e}'. Enviando para DLQ.")
                raise

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