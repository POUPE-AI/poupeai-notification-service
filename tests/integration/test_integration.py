import pytest
import asyncio
import json
import aio_pika
from uuid import uuid4
from datetime import datetime, UTC
import redis.asyncio as aioredis

from config import settings

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

@pytest.fixture(autouse=True)
async def setup_rabbitmq_topology():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()

        exchange_main = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_MAIN, 
            type=aio_pika.ExchangeType.DIRECT,
            durable=True
        )
        
        exchange_dlq = await channel.declare_exchange(
            settings.RABBITMQ_EXCHANGE_DLQ,
            type=aio_pika.ExchangeType.DIRECT,
            durable=True
        )

        queue_dlq = await channel.declare_queue(
            settings.RABBITMQ_QUEUE_DLQ, 
            durable=True
        )
        
        queue_main = await channel.declare_queue(
            settings.RABBITMQ_QUEUE_MAIN,
            durable=True
        )

        await queue_dlq.bind(exchange_dlq, routing_key="#")
        await queue_main.bind(exchange_main, routing_key=settings.RABBITMQ_ROUTING_KEY)

        await queue_main.purge()
        await queue_dlq.purge()


async def publish_message(body_dict, routing_key=settings.RABBITMQ_ROUTING_KEY):

    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        exchange = await channel.declare_exchange(settings.RABBITMQ_EXCHANGE_MAIN, durable=True)

        message_body = json.dumps(body_dict, default=str).encode('utf-8')
        message = aio_pika.Message(
            body=message_body,
            content_type="application/json",
            correlation_id=str(uuid4()),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT
        )
        await exchange.publish(message, routing_key=routing_key)


async def check_idempotency_key_exists(message_id):
    redis_client = aioredis.from_url(settings.REDIS_URL)
    key = f"idempotency:{message_id}"
    try:
        exists = await redis_client.exists(key)
        return exists > 0
    finally:
        await redis_client.aclose()


async def get_message_from_dlq():
    connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.RABBITMQ_QUEUE_DLQ, durable=True)

        try:
            message = await queue.get(fail=False)
            if message:
                await message.ack()
                return json.loads(message.body.decode())
            return None
        except Exception:
            return None


@pytest.fixture
def valid_payload():
    return {
        "message_id": str(uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "trigger_type": "integration_test",
        "event_type": "INVOICE_DUE_SOON",
        "recipient": {
            "user_id": "integration-user",
            "email": "integration@test.com",
            "name": "Int User"
        },
        "payload": {
            "credit_card": "Visa",
            "month": 12,
            "year": 2025,
            "due_date": "2025-12-25",
            "amount": 100.00,
            "invoice_deep_link": "app://invoice"
        }
    }


async def test_it001_consume_valid_message_successfully(valid_payload):

    msg_id = valid_payload['message_id']

    await publish_message(valid_payload)

    await asyncio.sleep(5)

    is_processed = await check_idempotency_key_exists(msg_id)
    assert is_processed is True, "A chave de idempotência deveria existir no Redis"


async def test_it003_invalid_event_goes_to_dlq(valid_payload):

    valid_payload['event_type'] = "EVENTO_QUE_NAO_EXISTE"
    valid_payload['message_id'] = str(uuid4())  # Novo ID

    while await get_message_from_dlq():
        pass

    await publish_message(valid_payload)

    await asyncio.sleep(5)

    dlq_message = await get_message_from_dlq()
    assert dlq_message is not None, "Deveria haver uma mensagem na DLQ"
    assert dlq_message['message_id'] == valid_payload['message_id']
