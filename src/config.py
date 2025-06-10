from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Notification Service"
    version: str = "0.0.1"
    debug: bool = True
    host: str = "localhost"
    port: int = 8000

settings = Settings() 