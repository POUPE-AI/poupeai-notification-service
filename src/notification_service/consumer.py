import asyncio
from aio_pika.abc import AbstractIncomingMessage
from config import settings

class RabbitMQConsumer:
    def __init__(self):
        self.rabbitmq_url = settings.RABBITMQ_URL
        print("Consumidor RabbitMQ inicializado.")

    async def connect(self):
        print("Método connect chamado (ainda não implementado).")
        pass

    async def _setup_queues(self):
        print("Método _setup_queues chamado (ainda não implementado).")
        pass

    async def _on_message(self, message: AbstractIncomingMessage):
        print("Método _on_message chamado (ainda não implementado).")
        pass

    async def run(self):
        print("Iniciando a execução do consumidor...")
        await self.connect()
        await self._setup_queues()
        print("Consumidor está 'rodando' (implementação pendente).")
        await asyncio.Future()