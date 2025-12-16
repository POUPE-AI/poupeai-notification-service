import asyncio
import aio_pika
import json
import structlog
from uuid import uuid4

from aio_pika.abc import AbstractIncomingMessage
from config import settings
from .exceptions import EventTypeValidationError, SchemaValidationError, TemplateRenderingError, TransientProcessingError
from .service import EventHandler

from datetime import datetime

logger = structlog.get_logger(__name__)

class RabbitMQConsumer:
    MAX_RETRIES = settings.RABBITMQ_MAX_RETRIES

    def __init__(self, event_handler: EventHandler):
        self.rabbitmq_url = settings.RABBITMQ_URL
        self.event_handler = event_handler
        self._connection = None
        self._channel = None
        logger.debug(
            "RabbitMQ consumer initialized",
            event_type="RABBITMQ_CONSUMER_INITIALIZED",
            trigger_type="system_scheduled",
            rabbitmq_url=self.rabbitmq_url,
        )

    async def connect(self):
        retry_interval = 5
        logger.debug(
            "Attempting to connect to RabbitMQ",
            event_type="RABBITMQ_CONNECT_ATTEMPT",
            trigger_type="system_scheduled",
            rabbitmq_url=self.rabbitmq_url,
        )
    
        while True:
            try:
                self._connection = await aio_pika.connect_robust(self.rabbitmq_url)
                self._channel = await self._connection.channel()
                logger.debug(
                    "RabbitMQ connection established successfully",
                    event_type="RABBITMQ_CONNECTED_SUCCESSFULLY",
                    trigger_type="system_scheduled",
                    rabbitmq_url=self.rabbitmq_url,
                )
                return
            except Exception as e:
                logger.error(
                    "Failed to connect to RabbitMQ. Retrying...",
                    event_type="RABBITMQ_CONNECTION_FAILED",
                    trigger_type="system_scheduled",
                    error=str(e),
                    retry_in_seconds=retry_interval,
                    rabbitmq_url=self.rabbitmq_url,
                    exc_info=e,
                )
                await asyncio.sleep(retry_interval)

    async def _setup_queues(self):
        if not self._channel:
            raise ConnectionError("Communication channel not available.")

        logger.debug(
            "Starting RabbitMQ topology setup",
            event_type="RABBITMQ_TOPOLOGY_SETUP_STARTING",
            trigger_type="system_scheduled"
        )

        try:
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

            logger.debug(
                "RabbitMQ topology setup finished successfully",
                event_type="RABBITMQ_TOPOLOGY_SETUP_FINISHED",
                trigger_type="system_scheduled",
                event_details={
                    "exchanges": {
                        "main": settings.RABBITMQ_EXCHANGE_MAIN,
                        "retry": settings.RABBITMQ_EXCHANGE_RETRY,
                        "dlx": settings.RABBITMQ_EXCHANGE_DLQ,
                    },
                    "queues": {
                        "main": settings.RABBITMQ_QUEUE_MAIN,
                        "retry": settings.RABBITMQ_QUEUE_RETRY,
                        "dlq": settings.RABBITMQ_QUEUE_DLQ,
                    }
                }
            )
        except Exception as e:
            logger.error(
                "Failed to set up RabbitMQ topology",
                event_type="RABBITMQ_TOPOLOGY_SETUP_FAILED",
                trigger_type="system_scheduled",
                error=str(e),
                exc_info=e
            )
            raise

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
                "Message successfully received and deserialized",
                event_type="MESSAGE_RECEIVED",
                trigger_type=event_data.get("trigger_type"),
                actor_user_id=event_data.get("recipient", {}).get("user_id"),
                event_details={
                    "queue": self.main_queue.name,
                    "retry_count": retry_count,
                    "routing_key": message.routing_key,
                    "message_size_bytes": len(message.body),
                }
            )
        
            await self.event_handler.process_event(event_data, correlation_id)
            processed_in_ms = None
            event_ts_str = event_data.get("timestamp")
            if event_ts_str:
                try:
                    event_ts = datetime.fromisoformat(event_ts_str.replace("Z", "+00:00"))
                    now = datetime.utcnow().timestamp()
                    processed_in_ms = (now - event_ts.timestamp()) * 1000
                except Exception as e:
                    log.warning("Failed to parse event timestamp from body", error=str(e))

            log.info(
                "Message processed successfully",
                event_type="MESSAGE_PROCESSED_SUCCESSFULLY",
                trigger_type=event_data.get("trigger_type"),
                actor_user_id=event_data.get("recipient", {}).get("user_id"),
                event_details={
                    "processed_in_ms": processed_in_ms,
                }
            )
            # ---------------------------------------------------------
            # [MUTANTE M5] - Omissão de Chamada
            # Objetivo: Simular o esquecimento do 'ack'.
            # Teste Alvo: test_ut003... (qualquer teste de sucesso verifica se o ack foi chamado)
            # ---------------------------------------------------------
            
            # [CÓDIGO ORIGINAL]
            await message.ack()

            # [CÓDIGO MUTADO - Descomente abaixo e comente o original]
            # pass # await message.ack()

        except (EventTypeValidationError, SchemaValidationError, json.JSONDecodeError, TemplateRenderingError) as e:
            log.error(
                "Unrecoverable error processing message. Moving to DLQ.",
                event_type="MESSAGE_SENT_TO_DLQ",
                trigger_type=event_data.get("trigger_type", "unknown"),
                actor_user_id=event_data.get("recipient", {}).get("user_id"),
                reason=f"Exception type: {type(e).__name__}",
                event_details={
                    "error_message": str(e),
                },
                exc_info=e
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

            # ---------------------------------------------------------
            # [MUTANTE M3] - Operador Relacional
            # Objetivo: Testar erro de "off-by-one" no retry.
            # Teste Alvo: test_ut010_max_retries_sends_to_dlq
            # ---------------------------------------------------------

            # [CÓDIGO ORIGINAL]
            if retry_count < self.MAX_RETRIES:
            
            # [CÓDIGO MUTADO - Descomente abaixo e comente o original]
            # if retry_count <= self.MAX_RETRIES:

                log.warning(
                    "Transient error occurred. Scheduling message for retry.",
                    event_type="MESSAGE_RETRY_SCHEDULED",
                    **log_details,
                    event_details={
                        "current_attempt": retry_count + 1,
                        "max_retries": self.MAX_RETRIES,
                        "error_message": str(e)
                    },
                    exc_info=e
                )
                republished_message = self._republish_message(message)

                # ---------------------------------------------------------
                # [MUTANTE M4] - Troca de Variável
                # Objetivo: Simular envio para a exchange errada (DLQ em vez de Retry).
                # Teste Alvo: test_ut003_transient_error_schedules_retry
                # ---------------------------------------------------------

                # [CÓDIGO ORIGINAL]
                await self.retry_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
                
                # [CÓDIGO MUTADO - Descomente abaixo e comente o original]
                # await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            else:
                log.error(
                    f"Max retries ({self.MAX_RETRIES}) reached. Moving message to DLQ.",
                    event_type="MESSAGE_SENT_TO_DLQ_MAX_RETRIES",
                    **log_details,
                    event_details={
                        "last_error_message": str(e),
                    },
                    exc_info=e
                )
                republished_message = self._republish_message(message)
                await self.dlx_exchange.publish(republished_message, routing_key=settings.RABBITMQ_ROUTING_KEY)
            await message.ack()
    
    async def run(self):
        try:
            await self.connect()
            await self._setup_queues()
        
            logger.debug(
                "Consumer is ready and starting to consume messages",
                event_type="CONSUMER_STARTED_SUCCESSFULLY",
                trigger_type="system_scheduled",
                event_details={
                    "main_queue_name": self.main_queue.name
                }
            )
        
            await self.main_queue.consume(self._on_message)
            await asyncio.Future()
        
        except Exception as e:
            logger.error(
                "An unexpected error occurred during consumer runtime. Shutting down.",
                event_type="CONSUMER_RUNTIME_ERROR",
                trigger_type="system_scheduled",
                error=str(e),
                exc_info=e
            )
            raise
        
        finally:
            if self._connection and not self._connection.is_closed:
                await self._connection.close()
                logger.debug(
                    "RabbitMQ connection successfully closed",
                    event_type="RABBITMQ_CONNECTION_CLOSED",
                    trigger_type="system_scheduled"
                )