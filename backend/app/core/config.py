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
    DEBUG: bool = False

    # --- API ---
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # --- Security ---
    API_ENABLED: bool = Field(default=False, description="Enable API key authentication")
    API_KEY: str = Field(default="", description="Primary admin API key")
    API_KEY_READ: str = Field(default="", description="Read-only API key")
    API_KEY_WRITE: str = Field(default="", description="Read-write API key")
    
    # --- Rate Limiting ---
    RATE_LIMIT_ENABLED: bool = Field(default=False, description="Enable rate limiting")
    RATE_LIMIT_PER_MINUTE: int = Field(default=60, description="Requests per minute limit")
    RATE_LIMIT_PER_HOUR: int = Field(default=1000, description="Requests per hour limit")

    # --- Database (PostgreSQL) ---
    DATABASE_URL: str = "postgresql://edgebrain:edgebrain@postgres:5432/edgebrain"

    # --- Redis ---
    REDIS_URL: str = "redis://redis:6379/0"

    # --- MQTT ---
    MQTT_HOST: str = "mosquitto"
    MQTT_PORT: int = 1883
    MQTT_KEEPALIVE: int = 60

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (JSON array or comma-separated)",
    )

    # --- Simulator ---
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

    # --- Device Heartbeat ---
    DEVICE_HEARTBEAT_TIMEOUT_S: int = Field(default=60, description="Seconds before device marked offline")
    
    # --- Data Retention ---
    DATA_RETENTION_DAYS: int = Field(default=90, description="Days to retain sensor readings")
    DATA_CLEANUP_ENABLED: bool = Field(default=True, description="Enable automatic data cleanup")
    DATA_CLEANUP_INTERVAL_HOURS: int = Field(default=24, description="Hours between cleanup runs")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
