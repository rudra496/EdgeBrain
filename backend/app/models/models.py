import uuid
from datetime import datetime, timezone
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
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_readings_device_time", "device_id", "timestamp"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "device_type": self.device_type,
            "value": self.value,
            "unit": self.unit,
            "extra": self.extra,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class DeviceState(Base):
    __tablename__ = "device_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), unique=True, nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    room = Column(String(50), default="")
    value = Column(Float, default=0.0)
    unit = Column(String(20), default="")
    status = Column(String(20), default="online")  # online, offline, warning, critical
    last_seen = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_online = Column(Boolean, default=True)
    extra = Column(JSONB, default=dict)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "room": self.room,
            "value": self.value,
            "unit": self.unit,
            "status": self.status,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "is_online": self.is_online,
            "extra": self.extra,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ActuatorState(Base):
    __tablename__ = "actuator_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    actuator_type = Column(String(50), nullable=False)
    room = Column(String(50), default="")
    is_active = Column(Boolean, default=False)
    last_command = Column(String(100), default="")
    last_changed = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    extra = Column(JSONB, default=dict)

    __table_args__ = (
        Index("ix_actuator_device_type", "device_id", "actuator_type"),
    )

    def to_dict(self) -> dict:
        return {
            "device_id": self.device_id,
            "actuator_type": self.actuator_type,
            "room": self.room,
            "is_active": self.is_active,
            "last_command": self.last_command,
            "last_changed": self.last_changed.isoformat() if self.last_changed else None,
        }


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    command = Column(String(100), nullable=False)
    params = Column(JSONB, default=dict)
    source = Column(String(50), default="system")
    status = Column(String(20), default="sent")  # sent, delivered, executed, failed
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "command": self.command,
            "params": self.params,
            "source": self.source,
            "status": self.status,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)  # info, warning, critical
    message = Column(Text, nullable=False)
    value = Column(Float, default=0.0)
    threshold = Column(Float, default=0.0)
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    acknowledged_by = Column(String(100), nullable=True)
    resolved = Column(Boolean, default=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(String(100), nullable=True)
    resolution_note = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_alerts_device_time", "device_id", "timestamp"),
        Index("ix_alerts_severity", "severity"),
        Index("ix_alerts_resolved", "resolved"),
    )

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "device_id": self.device_id,
            "device_type": self.device_type,
            "severity": self.severity,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "resolution_note": self.resolution_note,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
