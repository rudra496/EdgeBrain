import logging
from dataclasses import dataclass
from app.ai.rules import Decision, DecisionEngine
from app.ai.anomaly import AnomalyDetector
from app.services.ingestion import data_ingestion
from app.services.execution import ExecutionService, AlertService
from app.core.mqtt_client import mqtt_client
from app.core.events import event_queue

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    sender: str
    target: str
    data: dict


class MultiAgentSystem:
    """Lightweight multi-agent system for edge intelligence."""

    def __init__(self):
        self.execution = ExecutionService(mqtt_client)
        self.alerts = AlertService()
        self.engine = DecisionEngine()
        self.engine.add_strategy(AnomalyDetector())
        self._message_log: list[AgentMessage] = []

    def _log_message(self, sender: str, target: str, data: dict):
        msg = AgentMessage(sender=sender, target=target, data=data)
        self._message_log.append(msg)
        if len(self._message_log) > 1000:
            self._message_log = self._message_log[-500:]

    def data_agent(self, device_id: str, device_type: str, value: float, unit: str, extra: dict):
        """Process and validate incoming sensor data."""
        # Validate
        if value < 0 and device_type in ("temperature", "energy"):
            logger.warning(f"Invalid value from {device_id}: {value}")
            return

        # Store
        reading = data_ingestion.process(device_id, device_type, value, unit, extra)
        self._log_message("data_agent", "decision_agent", {
            "device_id": device_id, "device_type": device_type, "value": value
        })

        # Pass to decision agent
        self.decision_agent(device_id, device_type, value)

    def decision_agent(self, device_id: str, device_type: str, value: float):
        """Evaluate rules and ML models."""
        history = data_ingestion.get_recent_readings(device_id, minutes=30, limit=100)
        history_values = [h["value"] for h in history]

        decisions = self.engine.evaluate(device_id, device_type, value, history_values)
        self._log_message("decision_agent", "action_agent", {
            "device_id": device_id, "decisions": len(decisions)
        })

        # Pass to action agent
        for decision in decisions:
            self.action_agent(decision)

    def action_agent(self, decision: Decision):
        """Execute decisions and create alerts."""
        if decision.severity in ("warning", "critical"):
            self.alerts.create_alert(
                device_id=decision.device_id,
                alert_type=decision.action,
                severity=decision.severity,
                message=decision.reason,
            )
            event_queue.push_alert({
                "device_id": decision.device_id,
                "type": decision.action,
                "severity": decision.severity,
                "message": decision.reason,
                "confidence": decision.confidence,
            })

        # Execute command
        actuator_id = decision.device_id.split("-")[0] + "-actuator-" + decision.params.get("actuator", "unknown")
        self.execution.send_command(
            device_id=actuator_id,
            command=decision.action,
            params=decision.params,
            source="ai_engine",
        )
        self._log_message("action_agent", "system", {
            "device_id": decision.device_id,
            "action": decision.action,
        })
        logger.info(f"[Action] {decision.action} → {decision.device_id}: {decision.reason}")

    def get_messages(self, limit: int = 50) -> list[dict]:
        return [
            {"sender": m.sender, "target": m.target, "data": m.data}
            for m in self._message_log[-limit:]
        ]


agents = MultiAgentSystem()
