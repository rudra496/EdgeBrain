import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, Integer, Boolean, Text, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(50), nullable=False, index=True)
    device_type = Column(String(50), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(20))
    extra = Column(JSON, default=dict)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class DeviceCommand(Base):
    __tablename__ = "device_commands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(50), nullable=False, index=True)
    command = Column(String(50), nullable=False)
    params = Column(JSON, default=dict)
    source = Column(String(50), default="system")
    executed = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(50), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), default="info")  # info, warning, critical
    message = Column(Text)
    data = Column(JSON, default=dict)
    resolved = Column(Boolean, default=False)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class DeviceState(Base):
    __tablename__ = "device_states"

    device_id = Column(String(50), primary_key=True)
    device_type = Column(String(50), nullable=False)
    is_online = Column(Boolean, default=True)
    last_reading = Column(Float)
    last_seen = Column(DateTime(timezone=True), default=datetime.utcnow)
    metadata_ = Column("metadata", JSON, default=dict)
