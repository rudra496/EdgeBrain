
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# --- Sensor Data ---


class SensorReadingOut(BaseModel):
    id: str
    device_id: str
    device_type: str
    value: float
    unit: str
    extra: dict = Field(default_factory=dict)
    timestamp: str


class ReadingQueryParams(BaseModel):
    device_id: Optional[str] = None
    device_type: Optional[str] = None
    minutes: int = Field(default=60, ge=1, le=10080)
    limit: int = Field(default=100, ge=1, le=10000)


# --- Device ---


class DeviceStateOut(BaseModel):
    device_id: str
    device_type: str
    room: str = ""
    value: float = 0.0
    unit: str = ""
    status: str = "online"
    last_seen: Optional[str] = None
    is_online: bool = True
    extra: dict = Field(default_factory=dict)
    updated_at: Optional[str] = None


# --- Actuator ---


class ActuatorStateOut(BaseModel):
    device_id: str
    actuator_type: str
    room: str = ""
    is_active: bool = False
    last_command: str = ""
    last_changed: Optional[str] = None


# --- Command ---


class CommandIn(BaseModel):
    command: str
    params: dict = Field(default_factory=dict)
    source: str = "system"


class CommandOut(BaseModel):
    id: str
    device_id: str
    command: str
    params: dict = Field(default_factory=dict)
    source: str = "system"
    status: str = "sent"
    timestamp: str


# --- Alert ---


class AlertOut(BaseModel):
    id: str
    device_id: str
    device_type: str
    severity: str
    message: str
    value: float = 0.0
    threshold: float = 0.0
    acknowledged: bool = False
    acknowledged_at: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolution_note: Optional[str] = None
    timestamp: str


class AlertAcknowledge(BaseModel):
    acknowledged_by: str = Field(..., min_length=1, max_length=100)


class AlertResolve(BaseModel):
    resolved_by: str = Field(..., min_length=1, max_length=100)
    resolution_note: Optional[str] = Field(default=None, max_length=1000)


# --- Prediction ---


class PredictionOut(BaseModel):
    device_id: str
    current_value: float
    anomaly_score: float
    predictions: dict
    moving_averages: dict


# --- Stats ---


class DeviceStatisticsOut(BaseModel):
    device_id: str
    minutes: int
    count: int
    mean: float
    std: float
    min: float
    max: float
    latest: float


class SystemStatsOut(BaseModel):
    total_devices: int
    online_devices: int
    offline_devices: int
    total_readings: int
    total_alerts: int
    total_commands: int
    uptime_seconds: float


# --- Heartbeat ---


class HeartbeatOut(BaseModel):
    total_devices: int
    online: int
    offline: int
    heartbeat_timeout_s: int
    offline_devices: list[dict] = Field(default_factory=list)


# --- Generic ---


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
