import logging
import threading
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, desc
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.heartbeat import device_heartbeat
from app.models.models import SensorReading, DeviceState, ActuatorState

logger = logging.getLogger(__name__)
settings = get_settings()


class DataIngestionService:
    """Ingests, validates, and stores sensor data. Provides query interface."""

    VALID_RANGES = {
        "temperature": (-40.0, 85.0),
        "motion": (0.0, 1.0),
        "energy": (0.0, 10000.0),
        "humidity": (0.0, 100.0),
        "light": (0.0, 100000.0),
    }

    def __init__(self):
        self._counters: dict[str, int] = {}
        self._cleanup_lock = threading.Lock()
        self._last_cleanup: datetime | None = None

    def ingest(self, device_id: str, device_type: str, value: float,
               unit: str = "", extra: dict | None = None) -> bool:
        """Validate and store a sensor reading."""
        extra = extra or {}

        # Range validation
        if device_type in self.VALID_RANGES:
            lo, hi = self.VALID_RANGES[device_type]
            if not (lo <= value <= hi):
                logger.warning(f"Out-of-range reading: {device_id}/{device_type}={value} (valid: {lo}..{hi})")
                return False

        # Update heartbeat
        device_heartbeat.update_heartbeat(device_id)

        db = SessionLocal()
        try:
            reading = SensorReading(
                device_id=device_id,
                device_type=device_type,
                value=value,
                unit=unit,
                extra=extra,
            )
            db.add(reading)

            # Upsert device state
            state = db.query(DeviceState).filter(DeviceState.device_id == device_id).first()
            if state:
                state.value = value
                state.unit = unit
                state.device_type = device_type
                state.last_seen = datetime.now(timezone.utc)
                state.is_online = True
                state.status = "online"
                state.updated_at = datetime.now(timezone.utc)
            else:
                state = DeviceState(
                    device_id=device_id,
                    device_type=device_type,
                    value=value,
                    unit=unit,
                    status="online",
                    is_online=True,
                    last_seen=datetime.now(timezone.utc),
                )
                db.add(state)

            db.commit()
            self._counters[device_type] = self._counters.get(device_type, 0) + 1

            # Periodic cleanup check
            self._maybe_run_cleanup()

            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Ingestion error for {device_id}: {e}")
            return False
        finally:
            db.close()

    def _maybe_run_cleanup(self):
        """Run data cleanup if enough time has passed since last run."""
        if not settings.DATA_CLEANUP_ENABLED:
            return

        now = datetime.now(timezone.utc)
        if self._last_cleanup:
            hours_since = (now - self._last_cleanup).total_seconds() / 3600
            if hours_since < settings.DATA_CLEANUP_INTERVAL_HOURS:
                return

        with self._cleanup_lock:
            # Double-check after acquiring lock
            if self._last_cleanup:
                hours_since = (datetime.now(timezone.utc) - self._last_cleanup).total_seconds() / 3600
                if hours_since < settings.DATA_CLEANUP_INTERVAL_HOURS:
                    return
            self._run_cleanup()

    def _run_cleanup(self):
        """Delete sensor readings older than the retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DATA_RETENTION_DAYS)
        db = SessionLocal()
        try:
            deleted = db.query(SensorReading).filter(SensorReading.timestamp < cutoff).delete()
            db.commit()
            if deleted > 0:
                logger.info(f"Data retention cleanup: deleted {deleted} readings older than {settings.DATA_RETENTION_DAYS} days")
            self._last_cleanup = datetime.now(timezone.utc)
        except Exception as e:
            db.rollback()
            logger.error(f"Cleanup error: {e}")
        finally:
            db.close()

    def cleanup_old_data(self, days: int | None = None) -> int:
        """Manually trigger cleanup. Returns number of deleted rows."""
        days = days or settings.DATA_RETENTION_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        db = SessionLocal()
        try:
            deleted = db.query(SensorReading).filter(SensorReading.timestamp < cutoff).delete()
            db.commit()
            logger.info(f"Manual cleanup: deleted {deleted} readings older than {days} days")
            return deleted
        except Exception as e:
            db.rollback()
            logger.error(f"Manual cleanup error: {e}")
            return 0
        finally:
            db.close()

    # ─── Query Interface ──────────────────────────────────

    def get_all_devices(self) -> list[dict]:
        db = SessionLocal()
        try:
            devices = db.query(DeviceState).all()
            return [d.to_dict() for d in devices]
        finally:
            db.close()

    def get_device(self, device_id: str) -> dict | None:
        db = SessionLocal()
        try:
            state = db.query(DeviceState).filter(DeviceState.device_id == device_id).first()
            return state.to_dict() if state else None
        finally:
            db.close()

    def get_recent_readings(self, device_id: str, minutes: int = 60, limit: int = 100) -> list[dict]:
        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            rows = (
                db.query(SensorReading)
                .filter(SensorReading.device_id == device_id, SensorReading.timestamp >= since)
                .order_by(desc(SensorReading.timestamp))
                .limit(limit)
                .all()
            )
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    def get_statistics(self, device_id: str, minutes: int = 60) -> dict:
        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            result = (
                db.query(
                    func.count(SensorReading.value).label("count"),
                    func.avg(SensorReading.value).label("mean"),
                    func.min(SensorReading.value).label("min"),
                    func.max(SensorReading.value).label("max"),
                )
                .filter(SensorReading.device_id == device_id, SensorReading.timestamp >= since)
                .first()
            )
            return {
                "device_id": device_id,
                "minutes": minutes,
                "count": result.count or 0,
                "mean": round(result.mean, 2) if result.mean else 0.0,
                "min": round(result.min, 2) if result.min else 0.0,
                "max": round(result.max, 2) if result.max else 0.0,
            }
        finally:
            db.close()

    def get_all_readings(self, device_type: str | None = None, minutes: int = 60, limit: int = 100) -> list[dict]:
        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            q = db.query(SensorReading).filter(SensorReading.timestamp >= since)
            if device_type:
                q = q.filter(SensorReading.device_type == device_type)
            rows = q.order_by(desc(SensorReading.timestamp)).limit(limit).all()
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    def get_all_actuators(self) -> list[dict]:
        db = SessionLocal()
        try:
            rows = db.query(ActuatorState).all()
            return [r.to_dict() for r in rows]
        finally:
            db.close()

    def get_device_summary(self) -> dict:
        db = SessionLocal()
        try:
            total = db.query(DeviceState).count()
            online = db.query(DeviceState).filter(DeviceState.is_online == True).count()
            return {
                "total_devices": total,
                "online_devices": online,
                "offline_devices": total - online,
            }
        finally:
            db.close()

    def get_ingestion_stats(self) -> dict:
        return {
            "counters": dict(self._counters),
            "total": sum(self._counters.values()),
            "data_retention_days": settings.DATA_RETENTION_DAYS,
            "cleanup_enabled": settings.DATA_CLEANUP_ENABLED,
            "last_cleanup": self._last_cleanup.isoformat() if self._last_cleanup else None,
        }


data_ingestion = DataIngestionService()
