import logging
from datetime import datetime, timezone
from sqlalchemy import desc, func
from app.core.database import SessionLocal
from app.core.mqtt_client import mqtt_client
from app.models.models import DeviceCommand, Alert, ActuatorState

logger = logging.getLogger(__name__)


class ExecutionService:
    """Sends commands to actuators via MQTT and tracks state."""

    def send_command(self, device_id: str, command: str, params: dict | None = None,
                     source: str = "system") -> dict | None:
        params = params or {}
        actuator_type = params.get("actuator", "unknown")

        db = SessionLocal()
        try:
            cmd = DeviceCommand(
                device_id=device_id,
                command=command,
                params=params,
                source=source,
                status="sent",
            )
            db.add(cmd)

            # Update actuator state
            actuator = (
                db.query(ActuatorState)
                .filter(ActuatorState.device_id == device_id, ActuatorState.actuator_type == actuator_type)
                .first()
            )
            if actuator:
                actuator.last_command = command
                actuator.last_changed = datetime.now(timezone.utc)
                if command in ("on", "start", "open"):
                    actuator.is_active = True
                elif command in ("off", "stop", "close"):
                    actuator.is_active = False
            else:
                actuator = ActuatorState(
                    device_id=device_id,
                    actuator_type=actuator_type,
                    room=params.get("room", ""),
                    is_active=command in ("on", "start", "open"),
                    last_command=command,
                )
                db.add(actuator)

            db.commit()

            # Publish via MQTT
            topic = f"edgebrain/devices/{device_id}/command"
            payload = {
                "command": command,
                "params": params,
                "source": source,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            mqtt_client.publish(topic, payload)

            logger.info(f"Command sent: {device_id} -> {command} ({params})")
            return cmd.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Command error for {device_id}: {e}")
            return None
        finally:
            db.close()

    def get_commands(self, minutes: int = 60, limit: int = 100) -> list[dict]:
        from datetime import timedelta

        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            rows = (
                db.query(DeviceCommand)
                .filter(DeviceCommand.timestamp >= since)
                .order_by(desc(DeviceCommand.timestamp))
                .limit(limit)
                .all()
            )
            return [c.to_dict() for c in rows]
        finally:
            db.close()


class AlertService:
    """Manages alert lifecycle: creation, acknowledgment, and resolution."""

    def create_alert(self, device_id: str, device_type: str, severity: str,
                     message: str, value: float = 0.0, threshold: float = 0.0) -> dict:
        db = SessionLocal()
        try:
            alert = Alert(
                device_id=device_id,
                device_type=device_type,
                severity=severity,
                message=message,
                value=value,
                threshold=threshold,
            )
            db.add(alert)
            db.commit()
            logger.warning(f"Alert [{severity}]: {device_id} - {message} (value={value}, threshold={threshold})")
            return alert.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Alert creation error: {e}")
            return {}
        finally:
            db.close()

    def acknowledge_alert(self, alert_id: str, acknowledged_by: str) -> dict | None:
        """Acknowledge an alert."""
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return None
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            db.commit()
            logger.info(f"Alert {alert_id} acknowledged by {acknowledged_by}")
            return alert.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Alert acknowledge error: {e}")
            return None
        finally:
            db.close()

    def resolve_alert(self, alert_id: str, resolved_by: str, resolution_note: str | None = None) -> dict | None:
        """Resolve an alert."""
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if not alert:
                return None
            alert.resolved = True
            alert.resolved_at = datetime.now(timezone.utc)
            alert.resolved_by = resolved_by
            alert.resolution_note = resolution_note
            # Auto-acknowledge if not already
            if not alert.acknowledged:
                alert.acknowledged = True
                alert.acknowledged_at = datetime.now(timezone.utc)
                alert.acknowledged_by = resolved_by
            db.commit()
            logger.info(f"Alert {alert_id} resolved by {resolved_by}")
            return alert.to_dict()
        except Exception as e:
            db.rollback()
            logger.error(f"Alert resolve error: {e}")
            return None
        finally:
            db.close()

    def get_alerts(self, severity: str | None = None, resolved: bool | None = None,
                   minutes: int = 1440, limit: int = 100) -> list[dict]:
        from datetime import timedelta

        db = SessionLocal()
        try:
            since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
            q = db.query(Alert).filter(Alert.timestamp >= since)
            if severity:
                q = q.filter(Alert.severity == severity)
            if resolved is not None:
                q = q.filter(Alert.resolved == resolved)
            rows = q.order_by(desc(Alert.timestamp)).limit(limit).all()
            return [a.to_dict() for a in rows]
        finally:
            db.close()

    def get_stats(self) -> dict:
        db = SessionLocal()
        try:
            total = db.query(Alert).count()
            unresolved = db.query(Alert).filter(Alert.resolved == False).count()
            unacknowledged = db.query(Alert).filter(Alert.acknowledged == False).count()
            critical = db.query(Alert).filter(Alert.severity == "critical", Alert.resolved == False).count()
            warning = db.query(Alert).filter(Alert.severity == "warning", Alert.resolved == False).count()
            return {
                "total": total,
                "unresolved": unresolved,
                "unacknowledged": unacknowledged,
                "active_critical": critical,
                "active_warning": warning,
                "resolved": total - unresolved,
            }
        finally:
            db.close()


execution_service = ExecutionService()
alert_service = AlertService()
