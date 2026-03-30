import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.core.database import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20), default="")
    extra = Column(JSONB, default=dict)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_readings_device_ts", "device_id", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "device_type": self.device_type,
            "value": self.value,
            "unit": self.unit,
            "extra": self.extra or {},
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    command = Column(String(50), nullable=False)
    params = Column(JSONB, default=dict)
    source = Column(String(50), default="system")
    status = Column(String(20), default="pending")  # pending, sent, failed
    response = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "command": self.command,
            "params": self.params or {},
            "source": self.source,
            "status": self.status,
            "response": self.response,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="info")
    message = Column(Text)
    data = Column(JSONB, default=dict)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("idx_alerts_severity_ts", "severity", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "message": self.message,
            "data": self.data or {},
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class DeviceState(Base):
    __tablename__ = "device_states"

    device_id = Column(String(100), primary_key=True)
    device_type = Column(String(50), nullable=False)
    room = Column(String(50), default="default")
    is_online = Column(Boolean, default=True)
    last_reading = Column(Float)
    last_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    total_readings = Column(Integer, default=0)
    metadata_ = Column("metadata", JSONB, default=dict)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "room": self.room,
            "is_online": self.is_online,
            "last_reading": self.last_reading,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "total_readings": self.total_readings,
        }


class ActuatorState(Base):
    __tablename__ = "actuator_states"

    device_id = Column(String(100), primary_key=True)
    actuator_type = Column(String(50), nullable=False)  # alarm, fan, light
    room = Column(String(50), default="default")
    is_active = Column(Boolean, default=False)
    last_command = Column(String(50), nullable=True)
    last_changed = Column(DateTime(timezone=True), default=datetime.utcnow)
    metadata_ = Column("metadata", JSONB, default=dict)

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "actuator_type": self.actuator_type,
            "room": self.room,
            "is_active": self.is_active,
            "last_command": self.last_command,
            "last_changed": self.last_changed.isoformat() if self.last_changed else None,
        }
