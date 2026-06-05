from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for EdgeBrain.

    Values load from environment variables and optionally from a local `.env` file.
    This keeps Docker Compose, local dev, and CI behavior consistent.
    """

    # --- App ---
    APP_NAME: str = "EdgeBrain"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # --- API ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Comma-separated list (or JSON array) of allowed origins.
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["*"])

    # --- Database ---
    DATABASE_URL: str = "postgresql://edgebrain:edgebrain@postgres:5432/edgebrain"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- MQTT ---
    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60

    # --- Simulation ---
    SIM_INTERVAL_MS: int = 2000
    SIM_TEMP_BASE: float = 24.0
    SIM_TEMP_DRIFT: float = 0.3
    SIM_ENERGY_BASE: float = 120.0
    SIM_SPIKE_PROB: float = 0.01
    SIM_MOTION_PROB: float = 0.3

    # --- AI Engine ---
    ANOMALY_WINDOW: int = 100
    ANOMALY_Z_THRESHOLD: float = 2.0

    # --- Alerting ---
    TEMP_CRITICAL: float = 40.0
    TEMP_HIGH: float = 30.0
    TEMP_NORMAL: float = 25.0
    ENERGY_SPIKE: float = 500.0
    NO_MOTION_TIMEOUT_S: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
