import logging
from collections import deque
from datetime import datetime, timezone
import numpy as np
from scipy import stats as scipy_stats
from app.ai.rules import Decision, DecisionStrategy

logger = logging.getLogger(__name__)


class AnomalyDetector(DecisionStrategy):
    """Statistical anomaly detection using multiple methods.

    Methods:
    - Z-Score: detects values deviating from rolling mean
    - IQR: detects outliers beyond quartile boundaries
    - Gradient: detects sudden changes between consecutive readings

    All methods run on CPU with no model training required.
    """

    def __init__(self, window_size: int = 100, z_threshold: float = 2.0,
                 iqr_multiplier: float = 1.5, gradient_threshold: float = 3.0):
        self.window_size = window_size
        self.z_threshold = z_threshold
        self.iqr_multiplier = iqr_multiplier
        self.gradient_threshold = gradient_threshold
        self.history: dict[str, deque] = {}
        self._anomaly_count = 0

    def _get_history(self, device_id: str) -> deque:
        if device_id not in self.history:
            self.history[device_id] = deque(maxlen=self.window_size)
        return self.history[device_id]

    def _zscore(self, value: float, arr: np.ndarray) -> float:
        if len(arr) < 10:
            return 0.0
        mean = np.mean(arr)
        std = np.std(arr, ddof=1)
        if std < 1e-8:
            return 0.0
        return (value - mean) / std

    def _iqr_check(self, value: float, arr: np.ndarray) -> bool:
        if len(arr) < 10:
            return False
        q1 = np.percentile(arr, 25)
        q3 = np.percentile(arr, 75)
        iqr = q3 - q1
        lower = q1 - self.iqr_multiplier * iqr
        upper = q3 + self.iqr_multiplier * iqr
        return value < lower or value > upper

    def _gradient_check(self, value: float, arr: np.ndarray) -> float:
        if len(arr) < 3:
            return 0.0
        gradient = value - arr[-1]
        recent_std = np.std(arr[-10:], ddof=1) if len(arr) >= 10 else np.std(arr, ddof=1)
        if recent_std < 1e-8:
            return 0.0
        return abs(gradient / recent_std)

    def evaluate(self, device_id: str, device_type: str, value: float,
                 history: list[float]) -> list[Decision]:
        device_history = self._get_history(device_id)
        decisions = []

        if len(device_history) >= 10:
            arr = np.array(device_history)

            # Z-Score anomaly
            z = self._zscore(value, arr)
            z_anomaly = abs(z) > self.z_threshold

            # IQR anomaly
            iqr_anomaly = self._iqr_check(value, arr)

            # Gradient anomaly
            grad = self._gradient_check(value, arr)
            grad_anomaly = grad > self.gradient_threshold

            # Combine: require at least 2 methods to agree (reduces false positives)
            anomaly_methods = sum([z_anomaly, iqr_anomaly, grad_anomaly])

            if anomaly_methods >= 2:
                severity = "critical" if anomaly_methods == 3 else "warning"
                confidence = min(0.99, 0.5 + anomaly_methods * 0.15 + abs(z) * 0.05)

                anomaly_label = []
                if z_anomaly:
                    anomaly_label.append(f"z={z:.2f}")
                if iqr_anomaly:
                    anomaly_label.append("IQR")
                if grad_anomaly:
                    anomaly_label.append(f"grad={grad:.1f}")

                decisions.append(Decision(
                    action="activate",
                    device_id=device_id,
                    params={"actuator": "alarm"},
                    reason=f"Anomaly detected [{', '.join(anomaly_label)}] — {device_type}={value:.1f}",
                    confidence=round(confidence, 2),
                    severity=severity,
                    source=self.name,
                ))

                # Specific energy spike handling
                if device_type == "energy" and abs(z) > 2.5:
                    decisions.append(Decision(
                        action="activate",
                        device_id=device_id,
                        params={"actuator": "alarm"},
                        reason=f"Energy consumption anomaly (z={z:.2f}) — {value:.0f}W",
                        confidence=round(min(0.95, abs(z) / 3.0), 2),
                        severity="warning",
                        source=f"{self.name}:energy",
                    ))

        device_history.append(value)
        self._anomaly_count += len(decisions)
        return decisions

    def get_stats(self) -> dict:
        return {
            "devices_tracked": len(self.history),
            "total_anomalies": self._anomaly_count,
            "window_size": self.window_size,
            "z_threshold": self.z_threshold,
            "methods": ["z_score", "iqr", "gradient"],
        }

    @property
    def name(self) -> str:
        return "anomaly_detection"
