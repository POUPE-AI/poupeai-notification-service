from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')

    APP_NAME: str = "Notification Service"
    API_VERSION: str = "0.0.1"
    DEBUG: bool = True
    HOST: str = "localhost"
    PORT: int = 8001

    RABBITMQ_URL: str
    REDIS_URL: str
    SERVICE_NAME: str = APP_NAME

    EMAIL_HOST: str
    EMAIL_PORT: int
    EMAIL_LOGIN: str
    EMAIL_PASSWORD: SecretStr
    EMAIL_FROM: str
    EMAIL_FROM_NAME: str

settings = Settings()