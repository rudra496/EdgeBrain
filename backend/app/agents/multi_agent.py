import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.ai.rules import Decision, DecisionEngine, ThresholdStrategy, NoMotionStrategy
from app.ai.anomaly import AnomalyDetector
from app.ai.prediction import predictor
from app.services.ingestion import data_ingestion
from app.services.execution import execution_service, alert_service
from app.core.events import event_queue

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Internal message passed between agents."""
    id: str
    sender: str
    target: str
    msg_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "sender": self.sender,
            "target": self.target,
            "type": self.msg_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class MultiAgentSystem:
    """
    Multi-agent AI system for edge intelligence.

    Pipeline:
        Data Agent → validates & stores sensor data
        Decision Agent → evaluates rules & anomaly detection
        Action Agent → executes commands & creates alerts

    Agents communicate via internal message bus (in-memory).
    All messages are logged and queryable via API.
    """

    def __init__(self):
        self.engine = DecisionEngine()
        self.engine.add_strategy(ThresholdStrategy())
        self.engine.add_strategy(NoMotionStrategy(timeout_readings=150))
        self.engine.add_strategy(AnomalyDetector(window_size=100, z_threshold=2.0))

        self._messages: list[AgentMessage] = []
        self._msg_counter = 0
        self._processing_times: dict[str, list[float]] = {}
        self._readings_processed = 0

    def _send(self, sender: str, target: str, msg_type: str, data: dict) -> str:
        self._msg_counter += 1
        msg = AgentMessage(
            id=f"msg-{self._msg_counter:05d}",
            sender=sender,
            target=target,
            msg_type=msg_type,
            data=data,
        )
        self._messages.append(msg)
        if len(self._messages) > 2000:
            self._messages = self._messages[-1000:]

        logger.debug(f"[Agent] {sender} → {target}: {msg_type} ({data})")
        return msg.id

    def _track_time(self, agent: str, start: float):
        elapsed = (time.monotonic() - start) * 1000
        self._processing_times.setdefault(agent, []).append(elapsed)
        if len(self._processing_times[agent]) > 500:
            self._processing_times[agent] = self._processing_times[agent][-200:]

    # ─── Data Agent ──────────────────────────────────────────────

    def data_agent(self, device_id: str, device_type: str, value: float,
                   unit: str, extra: dict | None = None):
        """Validates, stores, and routes sensor data."""
        start = time.monotonic()

        # Validate via ingestion service (rejects out-of-range values)
        reading = data_ingestion.process(device_id, device_type, value, unit, extra)
        if reading is None:
            self._send("data_agent", "system", "rejected", {
                "device_id": device_id, "value": value, "reason": "out_of_range"
            })
            return

        self._readings_processed += 1
        self._track_time("data_agent", start)

        self._send("data_agent", "decision_agent", "evaluate", {
            "device_id": device_id,
            "device_type": device_type,
            "value": value,
        })

        # Pass to decision agent
        self.decision_agent(device_id, device_type, value)

    # ─── Decision Agent ──────────────────────────────────────────

    def decision_agent(self, device_id: str, device_type: str, value: float):
        """Evaluates all strategies and produces decisions."""
        start = time.monotonic()

        history = data_ingestion.get_recent_readings(device_id, minutes=30, limit=100)
        history_values = [h["value"] for h in history]

        decisions = self.engine.evaluate(device_id, device_type, value, history_values)
        self._track_time("decision_agent", start)

        self._send("decision_agent", "action_agent", "decisions", {
            "device_id": device_id,
            "decisions_count": len(decisions),
            "decisions": [d.to_dict() for d in decisions],
        })

        for decision in decisions:
            self.action_agent(decision)

    # ─── Action Agent ────────────────────────────────────────────

    def action_agent(self, decision: Decision):
        """Executes decisions: creates alerts + sends commands."""
        start = time.monotonic()

        # Create alert for warning/critical
        if decision.severity in ("warning", "critical"):
            alert_service.create_alert(
                device_id=decision.device_id,
                alert_type=f"{decision.action}_{decision.params.get('actuator', '')}",
                severity=decision.severity,
                message=decision.reason,
                data={"confidence": decision.confidence, "source": decision.source},
            )

        # Map device to actuator
        actuator_id = self._get_actuator_id(decision.device_id, decision.params.get("actuator"))

        # Send command
        result = execution_service.send_command(
            device_id=actuator_id,
            command=decision.action,
            params=decision.params,
            source=decision.source or "ai_engine",
        )

        self._track_time("action_agent", start)

        self._send("action_agent", "system", "executed", {
            "decision": decision.to_dict(),
            "command_sent": result is not None,
        })

        logger.info(f"[Action] {decision.action} → {actuator_id}: {decision.reason}")

    def _get_actuator_id(self, sensor_device_id: str, actuator_type: str) -> str:
        """Map sensor device ID to actuator device ID.

        Example: room-1-sensor-temp → room-1-actuator-alarm
        """
        parts = sensor_device_id.split("-sensor-")
        if len(parts) == 2:
            return f"{parts[0]}-actuator-{actuator_type}"
        return f"{sensor_device_id}-actuator-{actuator_type}"

    # ─── Query Methods ───────────────────────────────────────────

    def get_messages(self, limit: int = 50, agent: str | None = None) -> list[dict]:
        msgs = self._messages
        if agent:
            msgs = [m for m in msgs if m.sender == agent or m.target == agent]
        return [m.to_dict() for m in msgs[-limit:]]

    def get_stats(self) -> dict:
        avg_times = {}
        for agent, times in self._processing_times.items():
            avg_times[agent] = {
                "avg_ms": round(sum(times) / len(times), 2) if times else 0,
                "last_ms": round(times[-1], 2) if times else 0,
                "samples": len(times),
            }

        return {
            "readings_processed": self._readings_processed,
            "messages_in_bus": len(self._messages),
            "engine": self.engine.get_stats(),
            "agent_performance": avg_times,
        }


agents = MultiAgentSystem()
