from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Sensor Data ──────────────────────────────────────────

class SensorReadingOut(BaseModel):
    id: str
    device_id: str
    device_type: str
    value: float
    unit: str
    extra: dict = {}
    timestamp: str


class DeviceStateOut(BaseModel):
    device_id: str
    device_type: str
    room: str = "default"
    is_online: bool
    last_reading: Optional[float] = None
    last_seen: Optional[str] = None
    total_readings: int = 0


class DeviceStatistics(BaseModel):
    device_id: str
    period_minutes: int
    count: int
    avg: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    stddev: Optional[float] = None


# ─── Commands ────────────────────────────────────────────

class CommandOut(BaseModel):
    id: str
    device_id: str
    command: str
    params: dict = {}
    source: str
    status: str
    response: Optional[str] = None
    timestamp: str


class CommandIn(BaseModel):
    command: str = Field(..., description="activate or deactivate")
    params: dict = Field(default_factory=dict, description="e.g. {'actuator': 'fan'}")


class ActuatorStateOut(BaseModel):
    device_id: str
    actuator_type: str
    room: str = "default"
    is_active: bool
    last_command: Optional[str] = None
    last_changed: Optional[str] = None


# ─── Alerts ──────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    device_id: str
    alert_type: str
    severity: str
    message: str
    data: dict = {}
    resolved: bool
    resolved_at: Optional[str] = None
    timestamp: str


class AlertSummary(BaseModel):
    total: int
    unresolved: int
    critical_unresolved: int
    resolved: int


# ─── Agents ──────────────────────────────────────────────

class AgentMessageOut(BaseModel):
    id: str
    sender: str
    target: str
    type: str
    data: dict
    timestamp: str


class AgentStats(BaseModel):
    readings_processed: int
    messages_in_bus: int
    engine: dict
    agent_performance: dict


# ─── Prediction ──────────────────────────────────────────

class PredictionOut(BaseModel):
    value: float
    confidence: float
    method: str
    horizon: int
    details: dict


# ─── System ──────────────────────────────────────────────

class HealthCheck(BaseModel):
    status: str
    timestamp: str
    mqtt_connected: bool


class SystemStats(BaseModel):
    alerts: dict
    agents: dict
    ingestion: dict
    events: dict
    mqtt_connected: bool
    timestamp: str


class SystemInfo(BaseModel):
    name: str
    version: str
    components: dict
    mqtt_status: str


# ─── Generic ─────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None
