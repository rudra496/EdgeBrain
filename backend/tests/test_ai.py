"""EdgeBrain — AI-powered edge intelligence platform tests."""

import json
import pytest
from unittest.mock import MagicMock, patch
from app.ai.rules import ThresholdStrategy, NoMotionStrategy, DecisionEngine, Decision
from app.ai.anomaly import AnomalyDetector


class TestThresholdStrategy:
    def setup_method(self):
        self.strategy = ThresholdStrategy()

    def test_temperature_critical(self):
        decisions = self.strategy.evaluate("room-1", "temperature", 42.0, [])
        assert len(decisions) >= 1
        assert any(d.severity == "critical" and d.params["actuator"] == "alarm" for d in decisions)

    def test_temperature_high_fan(self):
        decisions = self.strategy.evaluate("room-1", "temperature", 32.0, [])
        assert any(d.action == "activate" and d.params["actuator"] == "fan" for d in decisions)

    def test_temperature_normal_fan_off(self):
        decisions = self.strategy.evaluate("room-1", "temperature", 22.0, [])
        assert any(d.action == "deactivate" and d.params["actuator"] == "fan" for d in decisions)

    def test_motion_detected(self):
        decisions = self.strategy.evaluate("room-1", "motion", 0.8, [])
        assert len(decisions) >= 1
        assert decisions[0].params["actuator"] == "light"

    def test_energy_spike(self):
        decisions = self.strategy.evaluate("room-1", "energy", 600.0, [])
        assert any(d.params["actuator"] == "alarm" for d in decisions)

    def test_unknown_device_type(self):
        decisions = self.strategy.evaluate("room-1", "pressure", 101.0, [])
        assert decisions == []

    def test_hysteresis_prevents_flapping(self):
        """After activation, deactivation requires lower threshold."""
        # Activate fan at 32°C
        self.strategy.evaluate("room-1", "temperature", 32.0, [])
        # At 26°C (above deactivate threshold of 25 but below 30 - 1.5 = 28.5), fan should still be on
        decisions = self.strategy.evaluate("room-1", "temperature", 26.0, [])
        # Should not deactivate yet (hysteresis)
        assert not any(d.action == "deactivate" and d.params["actuator"] == "fan" for d in decisions)

    def test_name(self):
        assert self.strategy.name == "threshold"


class TestNoMotionStrategy:
    def setup_method(self):
        self.strategy = NoMotionStrategy(timeout_readings=10)

    def test_no_motion_turns_off_lights(self):
        history = [0.0] * 10
        decisions = self.strategy.evaluate("room-1", "motion", 0.0, history)
        assert len(decisions) >= 1
        assert decisions[0].action == "deactivate"
        assert decisions[0].params["actuator"] == "light"

    def test_motion_keeps_lights_on(self):
        history = [0.0] * 8 + [0.8, 0.0]
        decisions = self.strategy.evaluate("room-1", "motion", 0.0, history)
        assert decisions == []

    def test_non_motion_device_ignored(self):
        decisions = self.strategy.evaluate("room-1", "temperature", 25.0, [25.0] * 10)
        assert decisions == []

    def test_insufficient_history(self):
        decisions = self.strategy.evaluate("room-1", "motion", 0.0, [0.0] * 5)
        assert decisions == []


class TestAnomalyDetector:
    def setup_method(self):
        self.detector = AnomalyDetector(window_size=100, z_threshold=2.0)

    def test_normal_values_no_anomaly(self):
        for v in [24.0, 24.5, 25.0, 24.8, 25.2, 24.9, 25.1, 24.7, 25.0, 24.8]:
            self.detector.evaluate("room-1", "temperature", v, [])
        decisions = self.detector.evaluate("room-1", "temperature", 25.0, [])
        assert decisions == []

    def test_spike_triggers_anomaly(self):
        # Establish baseline
        baseline = [25.0 + (i % 3 - 1) * 0.5 for i in range(50)]
        for v in baseline:
            self.detector.evaluate("room-1", "temperature", v, [])
        # Introduce massive spike
        decisions = self.detector.evaluate("room-1", "temperature", 55.0, baseline)
        assert len(decisions) >= 1
        assert decisions[0].severity in ("warning", "critical")

    def test_insufficient_data_no_anomaly(self):
        decisions = self.detector.evaluate("room-1", "temperature", 100.0, [])
        assert decisions == []

    def test_name(self):
        assert self.detector.name == "anomaly_detection"

    def test_stats(self):
        stats = self.detector.get_stats()
        assert "methods" in stats
        assert "z_score" in stats["methods"]


class TestDecisionEngine:
    def setup_method(self):
        self.engine = DecisionEngine()
        self.engine.add_strategy(ThresholdStrategy())

    def test_single_strategy(self):
        decisions = self.engine.evaluate("room-1", "temperature", 45.0, [])
        assert len(decisions) >= 1

    def test_multiple_strategies(self):
        self.engine.add_strategy(AnomalyDetector(window_size=5, z_threshold=1.0))
        decisions = self.engine.evaluate("room-1", "temperature", 45.0, [])
        assert len(decisions) >= 1

    def test_deduplication(self):
        """Same action + actuator from multiple strategies should be deduplicated."""
        decisions = self.engine.evaluate("room-1", "temperature", 45.0, [])
        keys = [f"{d.action}:{d.params.get('actuator')}:{d.device_id}" for d in decisions]
        assert len(keys) == len(set(keys))

    def test_stats(self):
        stats = self.engine.get_stats()
        assert "strategies" in stats
        assert "threshold" in stats["strategies"]

    def test_strategy_error_handling(self):
        class BrokenStrategy:
            name = "broken"
            def evaluate(self, *args):
                raise RuntimeError("boom")

        self.engine.add_strategy(BrokenStrategy())
        decisions = self.engine.evaluate("room-1", "temperature", 25.0, [])
        # Should not crash, just skip broken strategy
        assert isinstance(decisions, list)


class TestDecision:
    def test_to_dict(self):
        d = Decision(action="activate", device_id="test", params={"actuator": "fan"},
                     reason="test", confidence=0.9, severity="warning", source="test")
        ddict = d.to_dict()
        assert ddict["action"] == "activate"
        assert ddict["confidence"] == 0.9
        assert "timestamp" in ddict
