from pydantic import SecretStr, AmqpDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # Application
    APP_NAME: str = "Notification Service"
    SERVICE_NAME: str = "notification-service" 
    API_VERSION: str = "0.0.1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # RabbitMQ Connection
    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: SecretStr
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int
    RABBITMQ_MAX_RETRIES: int

    # RabbitMQ Topology
    RABBITMQ_EXCHANGE_MAIN: str
    RABBITMQ_EXCHANGE_RETRY: str
    RABBITMQ_EXCHANGE_DLQ: str

    RABBITMQ_QUEUE_MAIN: str
    RABBITMQ_QUEUE_RETRY: str
    RABBITMQ_QUEUE_DLQ: str

    RABBITMQ_ROUTING_KEY: str
    RABBITMQ_RETRY_DELAY_MS: int

    # Redis
    REDIS_URL: str

    # Email
    MAIL_USERNAME: Optional[str] = None
    MAIL_PASSWORD: Optional[SecretStr] = None
    MAIL_FROM: Optional[str] = None
    MAIL_FROM_NAME: Optional[str] = None
    MAIL_PORT: Optional[int] = None
    MAIL_SERVER: Optional[str] = None
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False

    @property
    def RABBITMQ_URL(self) -> AmqpDsn:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD.get_secret_value()}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

settings = Settings()