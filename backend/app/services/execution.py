import logging
from datetime import datetime
from app.core.database import SessionLocal
from app.models.models import DeviceCommand, Alert

logger = logging.getLogger(__name__)


class ExecutionService:
    """Sends commands to devices via MQTT and logs them."""

    def __init__(self, mqtt_client):
        self.mqtt = mqtt_client

    def send_command(self, device_id: str, command: str, params: dict = None, source: str = "system"):
        cmd = DeviceCommand(
            device_id=device_id,
            command=command,
            params=params or {},
            source=source,
            executed=False,
            timestamp=datetime.utcnow(),
        )

        db = SessionLocal()
        try:
            db.add(cmd)
            self.mqtt.publish(f"device/{device_id}/command", {
                "command": command,
                "params": params or {},
                "timestamp": datetime.utcnow().isoformat(),
            })
            cmd.executed = True
            db.commit()
            logger.info(f"Command '{command}' sent to {device_id}")
            return cmd
        except Exception as e:
            db.rollback()
            logger.error(f"Command failed for {device_id}: {e}")
            raise
        finally:
            db.close()


class AlertService:
    """Creates and manages alerts."""

    def create_alert(self, device_id: str, alert_type: str, severity: str, message: str, data: dict = None):
        alert = Alert(
            device_id=device_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            data=data or {},
            timestamp=datetime.utcnow(),
        )

        db = SessionLocal()
        try:
            db.add(alert)
            db.commit()
            db.refresh(alert)
            logger.warning(f"Alert [{severity}] {device_id}: {message}")
            return alert
        finally:
            db.close()

    def get_alerts(self, limit: int = 50, unresolved_only: bool = False) -> list[dict]:
        db = SessionLocal()
        try:
            query = db.query(Alert)
            if unresolved_only:
                query = query.filter(Alert.resolved == False)
            alerts = query.order_by(Alert.timestamp.desc()).limit(limit).all()
            return [
                {
                    "id": str(a.id),
                    "device_id": a.device_id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "message": a.message,
                    "resolved": a.resolved,
                    "timestamp": a.timestamp.isoformat(),
                }
                for a in alerts
            ]
        finally:
            db.close()
