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

        cmd = DeviceCommand(
            device_id=device_id,
            command=command,
            params=params,
            source=source,
            status="pending",
            timestamp=datetime.now(timezone.utc),
        )

        db = SessionLocal()
        try:
            db.add(cmd)

            # Publish via MQTT
            mqtt_client.publish(f"device/{device_id}/command", {
                "command": command,
                "params": params,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": source,
            })

            # Update actuator state
            state = db.query(ActuatorState).filter(
                ActuatorState.device_id == device_id
            ).first()
            if state is None:
                state = ActuatorState(
                    device_id=device_id,
                    actuator_type=actuator_type,
                    is_active=(command == "activate"),
                    last_command=command,
                    last_changed=datetime.now(timezone.utc),
                )
                db.add(state)
            else:
                state.is_active = (command == "activate")
                state.last_command = command
                state.last_changed = datetime.now(timezone.utc)

            cmd.status = "sent"
            db.commit()
            db.refresh(cmd)

            # Broadcast
            from app.core.events import event_queue
            event_queue.push_event("command", cmd.to_dict())

            logger.info(f"Command '{command}' sent to {device_id} (actuator: {actuator_type})")
            return cmd.to_dict()
        except Exception as e:
            db.rollback()
            if cmd.id:
                cmd.status = "failed"
                cmd.response = str(e)
                db.commit()
            logger.error(f"Command failed for {device_id}: {e}")
            return None
        finally:
            db.close()

    def get_commands(self, device_id: str | None = None, limit: int = 50) -> list[dict]:
        db = SessionLocal()
        try:
            query = db.query(DeviceCommand)
            if device_id:
                query = query.filter(DeviceCommand.device_id == device_id)
            cmds = query.order_by(desc(DeviceCommand.timestamp)).limit(limit).all()
            return [c.to_dict() for c in cmds]
        finally:
            db.close()

    def get_actuator_states(self) -> list[dict]:
        db = SessionLocal()
        try:
            states = db.query(ActuatorState).order_by(ActuatorState.device_id).all()
            return [s.to_dict() for s in states]
        finally:
            db.close()


class AlertService:
    """Creates, resolves, and queries alerts."""

    def create_alert(self, device_id: str, alert_type: str, severity: str,
                     message: str, data: dict | None = None) -> dict:
        alert = Alert(
            device_id=device_id,
            alert_type=alert_type,
            severity=severity,
            message=message,
            data=data or {},
            timestamp=datetime.now(timezone.utc),
        )

        db = SessionLocal()
        try:
            db.add(alert)
            db.commit()
            db.refresh(alert)
            result = alert.to_dict()

            # Push to Redis for real-time notification
            from app.core.events import event_queue
            event_queue.push_alert(result)

            return result
        except Exception as e:
            db.rollback()
            logger.error(f"Alert creation error: {e}")
            return {}
        finally:
            db.close()

    def resolve_alert(self, alert_id: str) -> bool:
        db = SessionLocal()
        try:
            alert = db.query(Alert).filter(Alert.id == alert_id).first()
            if alert:
                alert.resolved = True
                alert.resolved_at = datetime.now(timezone.utc)
                db.commit()
                return True
            return False
        finally:
            db.close()

    def resolve_device_alerts(self, device_id: str) -> int:
        db = SessionLocal()
        try:
            count = db.query(Alert).filter(
                Alert.device_id == device_id, Alert.resolved == False
            ).update({"resolved": True, "resolved_at": datetime.now(timezone.utc)})
            db.commit()
            return count
        finally:
            db.close()

    def get_alerts(self, limit: int = 50, unresolved_only: bool = False,
                   device_id: str | None = None, severity: str | None = None) -> list[dict]:
        db = SessionLocal()
        try:
            query = db.query(Alert)
            if unresolved_only:
                query = query.filter(Alert.resolved == False)
            if device_id:
                query = query.filter(Alert.device_id == device_id)
            if severity:
                query = query.filter(Alert.severity == severity)
            alerts = query.order_by(desc(Alert.timestamp)).limit(limit).all()
            return [a.to_dict() for a in alerts]
        finally:
            db.close()

    def get_alert_summary(self) -> dict:
        db = SessionLocal()
        try:
            total = db.query(func.count(Alert.id)).scalar() or 0
            unresolved = db.query(func.count(Alert.id)).filter(Alert.resolved == False).scalar() or 0
            critical = db.query(func.count(Alert.id)).filter(
                Alert.severity == "critical", Alert.resolved == False
            ).scalar() or 0

            return {
                "total": total,
                "unresolved": unresolved,
                "critical_unresolved": critical,
                "resolved": total - unresolved,
            }
        finally:
            db.close()


execution_service = ExecutionService()
alert_service = AlertService()
