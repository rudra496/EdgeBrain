import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    action: str
    device_id: str
    params: dict
    reason: str
    confidence: float
    severity: str = "info"


class DecisionStrategy(ABC):
    """Plugin interface for decision strategies."""

    @abstractmethod
    def evaluate(self, device_id: str, device_type: str, value: float, history: list[float]) -> list[Decision]:
        """Evaluate sensor data and return decisions."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class ThresholdStrategy(DecisionStrategy):
    """Rule-based threshold triggers."""

    def __init__(self):
        self.rules = {
            "temperature": [
                {"op": ">", "threshold": 40, "action": "activate", "params": {"actuator": "alarm"}, "reason": "Critical temperature", "severity": "critical", "confidence": 0.95},
                {"op": ">", "threshold": 30, "action": "activate", "params": {"actuator": "fan"}, "reason": "High temperature, fan ON", "severity": "warning", "confidence": 0.90},
                {"op": "<", "threshold": 25, "action": "deactivate", "params": {"actuator": "fan"}, "reason": "Temperature normal, fan OFF", "severity": "info", "confidence": 0.85},
            ],
            "motion": [
                {"op": ">", "threshold": 0.5, "action": "activate", "params": {"actuator": "light"}, "reason": "Motion detected, lights ON", "severity": "info", "confidence": 0.90},
            ],
            "energy": [
                {"op": ">", "threshold": 500, "action": "activate", "params": {"actuator": "alarm"}, "reason": "Energy spike detected", "severity": "warning", "confidence": 0.85},
            ],
        }

    def evaluate(self, device_id: str, device_type: str, value: float, history: list[float]) -> list[Decision]:
        decisions = []
        rules = self.rules.get(device_type, [])

        for rule in rules:
            threshold = rule["threshold"]
            triggered = False

            if rule["op"] == ">" and value > threshold:
                triggered = True
            elif rule["op"] == "<" and value < threshold:
                triggered = True
            elif rule["op"] == "==" and value == threshold:
                triggered = True

            if triggered:
                decisions.append(Decision(
                    action=rule["action"],
                    device_id=device_id,
                    params=rule["params"],
                    reason=rule["reason"],
                    confidence=rule["confidence"],
                    severity=rule["severity"],
                ))

        return decisions

    @property
    def name(self) -> str:
        return "threshold"


class DecisionEngine:
    """Evaluates data through all registered strategies."""

    def __init__(self):
        self.strategies: list[DecisionStrategy] = [ThresholdStrategy()]

    def add_strategy(self, strategy: DecisionStrategy):
        self.strategies.append(strategy)
        logger.info(f"Added strategy: {strategy.name}")

    def evaluate(self, device_id: str, device_type: str, value: float, history: list[float]) -> list[Decision]:
        all_decisions = []
        for strategy in self.strategies:
            try:
                decisions = strategy.evaluate(device_id, device_type, value, history)
                all_decisions.extend(decisions)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error: {e}")
        return all_decisions
