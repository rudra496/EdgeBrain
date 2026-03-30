import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc
from app.core.database import SessionLocal
from app.models.models import SensorReading, DeviceState, ActuatorState

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Ingests, validates, and stores sensor data. Provides query interface."""

    VALID_RANGES = {
        "temperature": (-40.0, 85.0),
        "motion": (0.0, 1.0),
        "energy": (0.0, 10000.0),
        "humidity": (0.0, 100.0),
        "light": (0.0, 100000.0),
        "co2": (0.0, 10000.0),
    }

    def __init__(self):
        self._counters: dict[str, int] = {}

    def _validate(self, device_type: str, value: float) -> bool:
        if device_type not in self.VALID_RANGES:
            return True  # unknown type, allow
        lo, hi = self.VALID_RANGES[device_type]
        return lo <= value <= hi

    def process(self, device_id: str, device_type: str, value: float, unit: str = "",
                extra: dict | None = None) -> dict | None:
        if not self._validate(device_type, value):
            logger.warning(f"Invalid reading rejected: {device_id} {device_type}={value}")
            return None

        reading = SensorReading(
            device_id=device_id,
            device_type=device_type,
            value=value,
            unit=unit,
            extra=extra or {},
            timestamp=datetime.now(timezone.utc),
        )

        db = SessionLocal()
        try:
            db.add(reading)

            # Upsert device state
            state = db.query(DeviceState).filter(DeviceState.device_id == device_id).first()
            if state is None:
                state = DeviceState(
                    device_id=device_id,
                    device_type=device_type,
                    is_online=True,
                    last_reading=value,
                    last_seen=datetime.now(timezone.utc),
                    total_readings=1,
                )
                db.add(state)
            else:
                state.last_reading = value
                state.last_seen = datetime.now(timezone.utc)
                state.is_online = True
                state.total_readings = (state.total_readings or 0) + 1

            db.commit()
            self._counters[device_id] = self._counters.get(device_id, 0) + 1

            # Broadcast to Redis for real-time
            from app.core.events import event_queue
            event_queue.push_telemetry(device_id, device_type, value, unit)

            return reading.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Ingestion error for {device_id}: {e}")
            return None
        finally:
            db.close()

    def get_recent_readings(self, device_id: str, minutes: int = 60, limit: int = 500) -> list[dict]:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            readings = (
                db.query(SensorReading)
                .filter(SensorReading.device_id == device_id, SensorReading.timestamp >= cutoff)
                .order_by(SensorReading.timestamp.asc())
                .limit(limit)
                .all()
            )
            return [r.to_dict() for r in readings]
        finally:
            db.close()

    def get_all_readings(self, device_type: str | None = None, minutes: int = 60,
                         limit: int = 1000) -> list[dict]:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            query = db.query(SensorReading).filter(SensorReading.timestamp >= cutoff)
            if device_type:
                query = query.filter(SensorReading.device_type == device_type)
            readings = query.order_by(SensorReading.timestamp.desc()).limit(limit).all()
            return [r.to_dict() for r in reversed(readings)]
        finally:
            db.close()

    def get_all_device_states(self) -> list[dict]:
        db = SessionLocal()
        try:
            states = db.query(DeviceState).order_by(DeviceState.device_id).all()
            return [s.to_dict() for s in states]
        finally:
            db.close()

    def get_statistics(self, device_id: str, minutes: int = 60) -> dict:
        db = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            result = db.query(
                func.count(SensorReading.id).label("count"),
                func.avg(SensorReading.value).label("avg"),
                func.min(SensorReading.value).label("min"),
                func.max(SensorReading.value).label("max"),
                func.stddev(SensorReading.value).label("stddev"),
            ).filter(
                SensorReading.device_id == device_id,
                SensorReading.timestamp >= cutoff,
            ).first()

            return {
                "device_id": device_id,
                "period_minutes": minutes,
                "count": result.count or 0,
                "avg": round(result.avg, 2) if result.avg else None,
                "min": round(result.min, 2) if result.min else None,
                "max": round(result.max, 2) if result.max else None,
                "stddev": round(result.stddev, 2) if result.stddev else None,
            }
        finally:
            db.close()

    def get_ingestion_stats(self) -> dict:
        return {
            "counters": dict(self._counters),
            "total": sum(self._counters.values()),
        }


data_ingestion = DataIngestionService()
