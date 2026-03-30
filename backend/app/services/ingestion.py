import logging
from datetime import datetime, timedelta
from app.core.database import SessionLocal
from app.models.models import SensorReading, DeviceState

logger = logging.getLogger(__name__)


class DataIngestionService:
    """Ingests sensor data, validates, and stores."""

    def __init__(self):
        self._last_values: dict[str, float] = {}

    def process(self, device_id: str, device_type: str, value: float, unit: str, extra: dict = None):
        reading = SensorReading(
            device_id=device_id,
            device_type=device_type,
            value=value,
            unit=unit,
            extra=extra or {},
            timestamp=datetime.utcnow(),
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
                    last_seen=datetime.utcnow(),
                )
                db.add(state)
            else:
                state.last_reading = value
                state.last_seen = datetime.utcnow()
                state.is_online = True

            db.commit()
            self._last_values[device_id] = value
            logger.debug(f"Ingested {device_type} from {device_id}: {value}{unit}")
            return reading
        except Exception as e:
            db.rollback()
            logger.error(f"Ingestion error for {device_id}: {e}")
            raise
        finally:
            db.close()

    def get_last_value(self, device_id: str) -> float | None:
        return self._last_values.get(device_id)

    def get_recent_readings(self, device_id: str, minutes: int = 60, limit: int = 500) -> list[dict]:
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(minutes=minutes)
            readings = (
                db.query(SensorReading)
                .filter(SensorReading.device_id == device_id, SensorReading.timestamp >= cutoff)
                .order_by(SensorReading.timestamp.desc())
                .limit(limit)
                .all()
            )
            return [
                {"value": r.value, "unit": r.unit, "timestamp": r.timestamp.isoformat()}
                for r in reversed(readings)
            ]
        finally:
            db.close()

    def get_all_device_states(self) -> list[dict]:
        db = SessionLocal()
        try:
            states = db.query(DeviceState).all()
            return [
                {
                    "device_id": s.device_id,
                    "device_type": s.device_type,
                    "is_online": s.is_online,
                    "last_reading": s.last_reading,
                    "last_seen": s.last_seen.isoformat() if s.last_seen else None,
                }
                for s in states
            ]
        finally:
            db.close()


data_ingestion = DataIngestionService()
