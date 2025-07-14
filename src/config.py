from pydantic import SecretStr, AmqpDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    APP_NAME: str = "Notification Service"
    API_VERSION: str = "0.0.1"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    RABBITMQ_USER: str
    RABBITMQ_PASSWORD: SecretStr
    RABBITMQ_HOST: str
    RABBITMQ_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int

    EMAIL_HOST: Optional[str] = None
    EMAIL_PORT: Optional[int] = None
    EMAIL_LOGIN: Optional[str] = None
    EMAIL_PASSWORD: Optional[SecretStr] = None
    EMAIL_FROM: Optional[str] = None
    
    @property
    def EMAIL_FROM_NAME(self) -> str:
        return self.APP_NAME

    @property
    def RABBITMQ_URL(self) -> AmqpDsn:
        return f"amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD.get_secret_value()}@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/"

    @property
    def REDIS_URL(self) -> RedisDsn:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"


settings = Settings()