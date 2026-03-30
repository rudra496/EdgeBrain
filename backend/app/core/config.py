from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "EdgeBrain"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://edgebrain:edgebrain@postgres:5432/edgebrain"

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # MQTT
    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
