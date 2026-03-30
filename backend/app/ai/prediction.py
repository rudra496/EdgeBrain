"""Prediction engine — lightweight CPU-based forecasting.

Implements:
- Linear Regression (ordinary least squares)
- Simple Moving Average (SMA)
- Exponential Moving Average (EMA)
- Multi-step forecasting
"""
import logging
import numpy as np
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    value: float
    confidence: float  # 0-1, based on fit quality
    method: str
    horizon: int  # steps ahead
    details: dict


class LinearRegression:
    """Simple OLS linear regression — no external ML libraries needed."""

    def fit(self, x: np.ndarray, y: np.ndarray):
        """Fit y = slope * x + intercept."""
        n = len(x)
        if n < 2:
            return None
        x_mean, y_mean = np.mean(x), np.mean(y)
        ss_xy = np.sum((x - x_mean) * (y - y_mean))
        ss_xx = np.sum((x - x_mean) ** 2)
        if ss_xx < 1e-10:
            return None
        slope = ss_xy / ss_xx
        intercept = y_mean - slope * x_mean
        # R-squared
        y_pred = slope * x + intercept
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - y_mean) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 1e-10 else 0
        residuals = y - y_pred
        std_err = np.std(residuals, ddof=1) if n > 2 else 0
        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": max(0, r_squared),
            "std_err": std_err,
        }

    def predict(self, model: dict, x_new: float) -> float:
        return model["slope"] * x_new + model["intercept"]


class Predictor:
    """Multi-method predictor for sensor time series."""

    MIN_HISTORY = 10
    FORECAST_STEPS = 10

    def __init__(self):
        self.lr = LinearRegression()

    def predict(self, values: list[float], steps: int = 1) -> list[PredictionResult]:
        if len(values) < self.MIN_HISTORY:
            return []

        arr = np.array(values, dtype=float)
        n = len(arr)
        results = []

        # Method 1: Linear Regression
        x = np.arange(n, dtype=float)
        model = self.lr.fit(x, arr)
        if model and model["r_squared"] > 0.1:
            for step in range(1, steps + 1):
                pred = self.lr.predict(model, n + step - 1)
                results.append(PredictionResult(
                    value=round(pred, 2),
                    confidence=round(model["r_squared"], 2),
                    method="linear_regression",
                    horizon=step,
                    details={"slope": round(model["slope"], 4), "r2": round(model["r_squared"], 3)},
                ))

        # Method 2: Simple Moving Average
        window = min(20, n // 2)
        if window >= 3:
            sma = np.convolve(arr, np.ones(window) / window, mode='valid')
            sma_trend = sma[-1] - sma[-2] if len(sma) >= 2 else 0
            sma_std = np.std(sma[-5:], ddof=1) if len(sma) >= 5 else np.std(sma, ddof=1)
            for step in range(1, steps + 1):
                pred = sma[-1] + sma_trend * step
                results.append(PredictionResult(
                    value=round(pred, 2),
                    confidence=round(max(0.1, 1.0 - (sma_std / (abs(sma[-1]) + 1e-8))), 2),
                    method="sma",
                    horizon=step,
                    details={"window": window, "trend": round(sma_trend, 4)},
                ))

        # Method 3: Exponential Moving Average
        alpha = 2.0 / (min(20, n // 2) + 1)
        ema = arr[0]
        for v in arr[1:]:
            ema = alpha * v + (1 - alpha) * ema
        ema_trend = ema - (alpha * arr[-2] + (1 - alpha) * ema) if n >= 2 else 0
        for step in range(1, steps + 1):
            pred = ema + ema_trend * step
            results.append(PredictionResult(
                value=round(pred, 2),
                confidence=0.6,
                method="ema",
                horizon=step,
                details={"alpha": round(alpha, 3)},
            ))

        return results

    def get_anomaly_score(self, values: list[float], current: float) -> float:
        """Get 0-1 anomaly score based on how far current deviates from predictions."""
        preds = self.predict(values, steps=1)
        if not preds:
            return 0.0
        best = max(preds, key=lambda p: p.confidence)
        if abs(best.value) < 1e-8:
            return 0.0
        deviation = abs(current - best.value) / (abs(best.value) * 0.2 + 1)
        return round(min(1.0, deviation), 3)

    def get_moving_averages(self, values: list[float]) -> dict:
        """Compute SMA and EMA for charting."""
        if len(values) < 3:
            return {}
        arr = np.array(values, dtype=float)
        result = {}

        # SMA with multiple windows
        for w in [5, 10, 20]:
            if len(arr) >= w:
                sma = np.convolve(arr, np.ones(w) / w, mode='valid')
                result[f"sma_{w}"] = sma.tolist()

        # EMA
        alpha = 0.1
        ema = [arr[0]]
        for v in arr[1:]:
            ema.append(alpha * v + (1 - alpha) * ema[-1])
        result["ema"] = ema

        return result


predictor = Predictor()
