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

    # Simulation
    SIM_INTERVAL_MS: int = 2000
    SIM_TEMP_BASE: float = 24.0
    SIM_TEMP_DRIFT: float = 0.3
    SIM_ENERGY_BASE: float = 120.0
    SIM_SPIKE_PROB: float = 0.01
    SIM_MOTION_PROB: float = 0.3

    # AI Engine
    ANOMALY_WINDOW: int = 100
    ANOMALY_Z_THRESHOLD: float = 2.0

    # Alerting
    TEMP_CRITICAL: float = 40.0
    TEMP_HIGH: float = 30.0
    TEMP_NORMAL: float = 25.0
    ENERGY_SPIKE: float = 500.0
    NO_MOTION_TIMEOUT_S: int = 300

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
