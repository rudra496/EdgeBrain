import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """A decision made by the AI engine."""
    action: str                          # "activate" or "deactivate"
    device_id: str                       # target device
    params: dict = field(default_factory=dict)
    reason: str = ""                     # human-readable explanation
    confidence: float = 0.0              # 0.0-1.0
    severity: str = "info"               # info, warning, critical
    source: str = ""                     # which strategy produced this
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "device_id": self.device_id,
            "params": self.params,
            "reason": self.reason,
            "confidence": self.confidence,
            "severity": self.severity,
            "source": self.source,
            "timestamp": self.timestamp,
        }


class DecisionStrategy(ABC):
    """Plugin interface for decision strategies.

    To create a custom strategy, subclass this and implement:
    - `name` property
    - `evaluate()` method
    """

    @abstractmethod
    def evaluate(self, device_id: str, device_type: str, value: float,
                 history: list[float]) -> list[Decision]:
        """Evaluate sensor data and return zero or more decisions."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this strategy."""
        pass


class ThresholdStrategy(DecisionStrategy):
    """Rule-based threshold triggers with hysteresis to prevent flapping.

    Thresholds are configurable per device type. Hysteresis prevents
    rapid on/off cycling around threshold boundaries.
    """

    DEFAULT_RULES = {
        "temperature": [
            {
                "op": ">", "threshold": 40.0, "hysteresis": 2.0,
                "action": "activate", "actuator": "alarm",
                "reason": "Critical temperature: {value}°C exceeds {threshold}°C",
                "severity": "critical", "confidence": 0.95,
            },
            {
                "op": "<", "threshold": 38.0,
                "action": "deactivate", "actuator": "alarm",
                "reason": "Temperature recovered: {value}°C below safe threshold",
                "severity": "info", "confidence": 0.90,
            },
            {
                "op": ">", "threshold": 30.0, "hysteresis": 1.5,
                "action": "activate", "actuator": "fan",
                "reason": "High temperature: {value}°C, fan activated",
                "severity": "warning", "confidence": 0.90,
            },
            {
                "op": "<", "threshold": 25.0,
                "action": "deactivate", "actuator": "fan",
                "reason": "Temperature normal: {value}°C, fan deactivated",
                "severity": "info", "confidence": 0.85,
            },
        ],
        "motion": [
            {
                "op": ">", "threshold": 0.5,
                "action": "activate", "actuator": "light",
                "reason": "Motion detected — lights ON",
                "severity": "info", "confidence": 0.90,
            },
        ],
        "energy": [
            {
                "op": ">", "threshold": 500.0,
                "action": "activate", "actuator": "alarm",
                "reason": "Energy spike: {value}W exceeds threshold",
                "severity": "warning", "confidence": 0.85,
            },
            {
                "op": "<", "threshold": 400.0,
                "action": "deactivate", "actuator": "alarm",
                "reason": "Energy normalized: {value}W",
                "severity": "info", "confidence": 0.80,
            },
        ],
    }

    def __init__(self, rules: dict | None = None):
        self.rules = rules or self.DEFAULT_RULES
        self._last_decisions: dict[str, str] = {}  # device_type -> last action

    def evaluate(self, device_id: str, device_type: str, value: float,
                 history: list[float]) -> list[Decision]:
        decisions = []
        rules = self.rules.get(device_type, [])
        last_action = self._last_decisions.get(device_type)

        for rule in rules:
            threshold = rule["threshold"]
            hysteresis = rule.get("hysteresis", 0)
            triggered = False

            effective_threshold = threshold
            # Apply hysteresis: if last action was "activate", require value to drop
            # below threshold - hysteresis before triggering "deactivate", and vice versa
            if last_action == "activate" and rule["action"] == "deactivate":
                effective_threshold = threshold - hysteresis
            elif last_action == "deactivate" and rule["action"] == "activate":
                effective_threshold = threshold + hysteresis

            if rule["op"] == ">" and value > effective_threshold:
                triggered = True
            elif rule["op"] == "<" and value < effective_threshold:
                triggered = True
            elif rule["op"] == "==" and abs(value - threshold) < 0.01:
                triggered = True

            if triggered:
                reason = rule["reason"].format(value=round(value, 1), threshold=threshold)
                decisions.append(Decision(
                    action=rule["action"],
                    device_id=device_id,
                    params={"actuator": rule.get("actuator", "unknown")},
                    reason=reason,
                    confidence=rule.get("confidence", 0.8),
                    severity=rule.get("severity", "info"),
                    source=self.name,
                ))
                self._last_decisions[device_type] = rule["action"]

        return decisions

    @property
    def name(self) -> str:
        return "threshold"


class NoMotionStrategy(DecisionStrategy):
    """Turns off lights when no motion detected for a configurable timeout."""

    def __init__(self, timeout_readings: int = 150):  # ~5 min at 2s interval
        self.timeout_readings = timeout_readings

    def evaluate(self, device_id: str, device_type: str, value: float,
                 history: list[float]) -> list[Decision]:
        if device_type != "motion" or not history:
            return []

        # Check last N readings
        recent = history[-self.timeout_readings:] if len(history) >= self.timeout_readings else history
        no_motion = all(v < 0.5 for v in recent)

        if no_motion and len(recent) >= self.timeout_readings:
            return [Decision(
                action="deactivate",
                device_id=device_id,
                params={"actuator": "light"},
                reason=f"No motion for {self.timeout_readings * 2}s — lights OFF",
                confidence=0.85,
                severity="info",
                source=self.name,
            )]

        return []

    @property
    def name(self) -> str:
        return "no_motion_timeout"


class DecisionEngine:
    """Orchestrates all decision strategies and aggregates results."""

    def __init__(self):
        self.strategies: list[DecisionStrategy] = []
        self._decision_count = 0

    def add_strategy(self, strategy: DecisionStrategy):
        self.strategies.append(strategy)
        logger.info(f"Added decision strategy: {strategy.name}")

    def evaluate(self, device_id: str, device_type: str, value: float,
                 history: list[float]) -> list[Decision]:
        all_decisions = []
        for strategy in self.strategies:
            try:
                decisions = strategy.evaluate(device_id, device_type, value, history)
                all_decisions.extend(decisions)
            except Exception as e:
                logger.error(f"Strategy '{strategy.name}' error: {e}")

        # Deduplicate: if multiple strategies suggest the same action for the same actuator,
        # keep only the highest confidence one
        deduped = self._deduplicate(all_decisions)
        self._decision_count += len(deduped)
        return deduped

    def _deduplicate(self, decisions: list[Decision]) -> list[Decision]:
        seen: dict[str, Decision] = {}
        for d in decisions:
            key = f"{d.action}:{d.params.get('actuator', '')}:{d.device_id}"
            if key not in seen or d.confidence > seen[key].confidence:
                seen[key] = d
        return list(seen.values())

    def get_stats(self) -> dict:
        return {
            "strategies": [s.name for s in self.strategies],
            "total_decisions": self._decision_count,
        }
