import logging
from collections import deque
import numpy as np
from app.ai.rules import Decision, DecisionStrategy

logger = logging.getLogger(__name__)


class AnomalyDetector(DecisionStrategy):
    """Z-score based anomaly detection — CPU only, no model training needed."""

    def __init__(self, window_size: int = 100, z_threshold: float = 2.0):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.history: dict[str, deque] = {}

    def _get_history(self, device_id: str) -> deque:
        if device_id not in self.history:
            self.history[device_id] = deque(maxlen=self.window_size)
        return self.history[device_id]

    def _compute_zscore(self, value: float, history: deque) -> float:
        if len(history) < 5:
            return 0.0
        arr = np.array(history)
        mean = np.mean(arr)
        std = np.std(arr)
        if std < 1e-8:
            return 0.0
        return abs((value - mean) / std)

    def evaluate(self, device_id: str, device_type: str, value: float, history: list[float]) -> list[Decision]:
        device_history = self._get_history(device_id)

        decisions = []
        if len(device_history) >= 5:
            z_score = self._compute_zscore(value, device_history)

            if z_score > self.z_threshold:
                severity = "critical" if z_score > 3.0 else "warning"
                decisions.append(Decision(
                    action="activate",
                    device_id=device_id,
                    params={"actuator": "alarm"},
                    reason=f"Anomaly detected (z={z_score:.2f}) — {device_type}={value:.1f}",
                    confidence=min(0.99, z_score / 3.0),
                    severity=severity,
                ))

            # Spike detection for energy
            if device_type == "energy" and z_score > 2.0:
                decisions.append(Decision(
                    action="activate",
                    device_id=device_id,
                    params={"actuator": "alarm"},
                    reason=f"Energy spike (z={z_score:.2f}) — {value:.1f}W",
                    confidence=min(0.95, z_score / 2.5),
                    severity="warning",
                ))

        device_history.append(value)
        return decisions

    @property
    def name(self) -> str:
        return "anomaly_detection"
