"""EdgeBrain — comprehensive test suite."""
import math
import pytest
from app.ai.rules import ThresholdStrategy, NoMotionStrategy, DecisionEngine, Decision
from app.ai.anomaly import AnomalyDetector
from app.ai.prediction import Predictor, LinearRegression


# ═══════════════════════════════════════════════════════════
# Threshold Strategy
# ═══════════════════════════════════════════════════════════

class TestThresholdStrategy:
    def setup_method(self):
        self.s = ThresholdStrategy()

    def test_temp_critical(self):
        d = self.s.evaluate("r1", "temperature", 42.0, [])
        assert any(x.severity == "critical" and x.params["actuator"] == "alarm" for x in d)

    def test_temp_fan_on(self):
        d = self.s.evaluate("r1", "temperature", 32.0, [])
        assert any(x.action == "activate" and x.params["actuator"] == "fan" for x in d)

    def test_temp_fan_off(self):
        self.s.evaluate("r1", "temperature", 32.0, [])  # activate first
        d = self.s.evaluate("r1", "temperature", 22.0, [])
        assert any(x.action == "deactivate" and x.params["actuator"] == "fan" for x in d)

    def test_motion_light_on(self):
        d = self.s.evaluate("r1", "motion", 0.8, [])
        assert any(x.params["actuator"] == "light" for x in d)

    def test_energy_spike(self):
        d = self.s.evaluate("r1", "energy", 600.0, [])
        assert any(x.params["actuator"] == "alarm" for x in d)

    def test_unknown_type_empty(self):
        assert self.s.evaluate("r1", "pressure", 101.0, []) == []

    def test_hysteresis(self):
        """Fan should NOT deactivate at 26°C when hysteresis is active."""
        self.s.evaluate("r1", "temperature", 32.0, [])
        d = self.s.evaluate("r1", "temperature", 26.0, [])
        assert not any(x.action == "deactivate" and x.params["actuator"] == "fan" for x in d)

    def test_name(self):
        assert self.s.name == "threshold"

    def test_all_decisions_have_source(self):
        d = self.s.evaluate("r1", "temperature", 50.0, [])
        assert all(x.source == "threshold" for x in d)

    def test_all_decisions_have_timestamp(self):
        d = self.s.evaluate("r1", "temperature", 50.0, [])
        assert all(x.timestamp for x in d)


# ═══════════════════════════════════════════════════════════
# No-Motion Strategy
# ═══════════════════════════════════════════════════════════

class TestNoMotionStrategy:
    def setup_method(self):
        self.s = NoMotionStrategy(timeout_readings=10)

    def test_no_motion_off(self):
        d = self.s.evaluate("r1", "motion", 0.0, [0.0] * 10)
        assert len(d) >= 1
        assert d[0].action == "deactivate"

    def test_has_motion_no_off(self):
        d = self.s.evaluate("r1", "motion", 0.0, [0.0] * 8 + [0.8, 0.0])
        assert d == []

    def test_non_motion_ignored(self):
        assert self.s.evaluate("r1", "temperature", 25.0, [25.0] * 10) == []

    def test_short_history(self):
        assert self.s.evaluate("r1", "motion", 0.0, [0.0] * 5) == []

    def test_name(self):
        assert self.s.name == "no_motion_timeout"


# ═══════════════════════════════════════════════════════════
# Anomaly Detector
# ═══════════════════════════════════════════════════════════

class TestAnomalyDetector:
    def setup_method(self):
        self.d = AnomalyDetector(window_size=100, z_threshold=2.0)

    def test_normal_no_anomaly(self):
        for v in [24.0, 24.5, 25.0, 24.8, 25.2, 24.9, 25.1, 24.7, 25.0, 24.8]:
            self.d.evaluate("r1", "temperature", v, [])
        assert self.d.evaluate("r1", "temperature", 25.0, []) == []

    def test_spike_detects(self):
        baseline = [25.0 + (i % 3 - 1) * 0.5 for i in range(50)]
        for v in baseline:
            self.d.evaluate("r1", "temperature", v, [])
        d = self.d.evaluate("r1", "temperature", 55.0, baseline)
        assert len(d) >= 1

    def test_insufficient_data(self):
        assert self.d.evaluate("r1", "temperature", 100.0, []) == []

    def test_stats(self):
        stats = self.d.get_stats()
        assert "methods" in stats
        assert len(stats["methods"]) == 3

    def test_name(self):
        assert self.d.name == "anomaly_detection"

    def test_severity_levels(self):
        baseline = [25.0] * 30
        for v in baseline:
            self.d.evaluate("r1", "temperature", v, [])
        d = self.d.evaluate("r1", "temperature", 60.0, baseline)
        if d:
            assert d[0].severity in ("warning", "critical")


# ═══════════════════════════════════════════════════════════
# Decision Engine
# ═══════════════════════════════════════════════════════════

class TestDecisionEngine:
    def setup_method(self):
        self.e = DecisionEngine()
        self.e.add_strategy(ThresholdStrategy())

    def test_single_strategy(self):
        assert len(self.e.evaluate("r1", "temperature", 45.0, [])) >= 1

    def test_multiple_strategies(self):
        self.e.add_strategy(AnomalyDetector(window_size=5, z_threshold=1.0))
        assert len(self.e.evaluate("r1", "temperature", 45.0, [])) >= 1

    def test_deduplication(self):
        d = self.e.evaluate("r1", "temperature", 45.0, [])
        keys = [f"{x.action}:{x.params.get('actuator')}:{x.device_id}" for x in d]
        assert len(keys) == len(set(keys))

    def test_error_handling(self):
        class BrokenStrategy:
            name = "broken"
            def evaluate(self, *a, **kw):
                raise RuntimeError("boom")
        self.e.add_strategy(BrokenStrategy())
        assert isinstance(self.e.evaluate("r1", "temperature", 25.0, []), list)

    def test_stats(self):
        self.e.evaluate("r1", "temperature", 45.0, [])
        s = self.e.get_stats()
        assert "strategies" in s
        assert s["total_decisions"] >= 1


# ═══════════════════════════════════════════════════════════
# Prediction Engine
# ═══════════════════════════════════════════════════════════

class TestPrediction:
    def setup_method(self):
        self.p = Predictor()

    def test_insufficient_data(self):
        assert self.p.predict([1.0, 2.0], 1) == []

    def test_linear_trend(self):
        values = [10 + i * 0.5 for i in range(30)]
        preds = self.p.predict(values, 1)
        assert len(preds) > 0
        lr_pred = next((p for p in preds if p.method == "linear_regression"), None)
        if lr_pred:
            assert lr_pred.value > 20  # should predict upward

    def test_flat_series(self):
        values = [25.0] * 30
        preds = self.p.predict(values, 1)
        assert len(preds) > 0

    def test_multi_step(self):
        values = list(range(20, 50))
        preds = self.p.predict(values, 5)
        lr_preds = [p for p in preds if p.method == "linear_regression"]
        assert len(lr_preds) == 5

    def test_anomaly_score(self):
        values = [25.0] * 30
        score = self.p.get_anomaly_score(values, 25.0)
        assert 0 <= score <= 1
        high_score = self.p.get_anomaly_score(values, 50.0)
        assert high_score > score

    def test_moving_averages(self):
        values = list(range(30))
        ma = self.p.get_moving_averages(values)
        assert "sma_5" in ma
        assert "ema" in ma
        assert len(ma["ema"]) == 30


class TestLinearRegression:
    def test_perfect_fit(self):
        lr = LinearRegression()
        x = np.array([0, 1, 2, 3, 4], dtype=float)
        y = np.array([0, 2, 4, 6, 8], dtype=float)
        model = lr.fit(x, y)
        assert model is not None
        assert abs(model["slope"] - 2.0) < 0.01
        assert abs(model["intercept"]) < 0.01
        assert model["r_squared"] > 0.99

    def test_no_variance(self):
        lr = LinearRegression()
        x = np.array([1, 1, 1], dtype=float)
        y = np.array([5, 5, 5], dtype=float)
        assert lr.fit(x, y) is None  # can't fit

    def test_predict(self):
        lr = LinearRegression()
        model = {"slope": 2.0, "intercept": 1.0}
        assert lr.predict(model, 5) == 11.0


# ═══════════════════════════════════════════════════════════
# Decision Model
# ═══════════════════════════════════════════════════════════

class TestDecision:
    def test_to_dict(self):
        d = Decision(action="activate", device_id="test", params={"actuator": "fan"},
                     reason="test", confidence=0.9, severity="warning", source="test")
        ddict = d.to_dict()
        assert ddict["action"] == "activate"
        assert ddict["confidence"] == 0.9
        assert "timestamp" in ddict

    def test_default_values(self):
        d = Decision(action="activate", device_id="test")
        assert d.params == {}
        assert d.confidence == 0.0
        assert d.severity == "info"
