"""EdgeBrain API tests — comprehensive endpoint testing with mocked services.

Uses FastAPI TestClient with mocked PostgreSQL, Redis, and MQTT to test
all REST endpoints and WebSocket without external dependencies.
"""
import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

# ─── Configure test environment before any app imports ──────────

os.environ.setdefault("DATABASE_URL", "sqlite:///test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("MQTT_HOST", "localhost")
os.environ["API_ENABLED"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ.setdefault("MQTT_PORT", "1883")

# Mock psycopg2 before sqlalchemy tries to import it
sys.modules.setdefault("psycopg2", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

from fastapi.testclient import TestClient


# ─── Patch targets (where services are used, not defined) ──────
# routes.py does: from app.services.ingestion import data_ingestion
# So we must patch at the usage site: app.api.routes.data_ingestion

PATCH_INGESTION = "app.api.routes.data_ingestion"
PATCH_EXECUTION = "app.api.routes.execution_service"
PATCH_ALERT = "app.api.routes.alert_service"
PATCH_AGENTS = "app.api.routes.agents"
PATCH_MQTT = "app.main.mqtt_client"
PATCH_EVENT_QUEUE = "app.main.event_queue"
PATCH_PREDICTOR = "app.api.routes.predictor"
PATCH_HEARTBEAT = "app.api.routes.device_heartbeat"
PATCH_AUTH_SERVICE = "app.api.routes.auth_service"

mock_mqtt = MagicMock()
mock_mqtt.is_connected = False


def _make_reading(device_id="room-1-sensor-temp", device_type="temperature",
                  value=25.0, unit="C"):
    return {
        "id": "test-uuid-001",
        "device_id": device_id,
        "device_type": device_type,
        "value": value,
        "unit": unit,
        "extra": {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _make_command(device_id="room-1-actuator-fan", command="activate",
                  status="sent"):
    return {
        "id": "cmd-uuid-001",
        "device_id": device_id,
        "command": command,
        "params": {"actuator": "fan"},
        "source": "api",
        "status": status,
        "response": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _make_alert(alert_id="alert-001", device_id="room-1-sensor-temp",
                severity="warning", resolved=False):
    return {
        "id": alert_id,
        "device_id": device_id,
        "alert_type": "activate_alarm",
        "severity": severity,
        "message": "Test alert",
        "data": {},
        "resolved": resolved,
        "resolved_at": None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _make_device_state(device_id="room-1-sensor-temp", device_type="temperature"):
    return {
        "device_id": device_id,
        "device_type": device_type,
        "room": "living-room",
        "is_online": True,
        "last_reading": 25.0,
        "last_seen": datetime.now(timezone.utc).isoformat(),
        "total_readings": 100,
    }


def _make_actuator_state(device_id="room-1-actuator-fan"):
    return {
        "device_id": device_id,
        "actuator_type": "fan",
        "room": "living-room",
        "is_active": False,
        "last_command": None,
        "last_changed": datetime.now(timezone.utc).isoformat(),
    }


# ─── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def mock_services():
    """Mock all external services for every test — patches at usage site."""
    mock_ing = MagicMock()
    mock_exec = MagicMock()
    mock_alert_svc = MagicMock()
    mock_ag = MagicMock()
    mock_eq = MagicMock()

    mock_ing.get_all_device_states.return_value = [
        _make_device_state("room-1-sensor-temp", "temperature"),
        _make_device_state("room-1-sensor-motion", "motion"),
    ]
    mock_ing.get_recent_readings.return_value = [
        _make_reading(value=25.0 + i * 0.5) for i in range(30)
    ]
    mock_ing.get_all_readings.return_value = [
        _make_reading(value=25.0 + i) for i in range(10)
    ]
    mock_ing.get_statistics.return_value = {
        "device_id": "room-1-sensor-temp",
        "period_minutes": 60,
        "count": 100,
        "avg": 25.5,
        "min": 22.0,
        "max": 28.0,
        "stddev": 1.2,
    }
    mock_ing.get_ingestion_stats.return_value = {
        "counters": {"room-1-sensor-temp": 100},
        "total": 100,
    }

    mock_exec.send_command.return_value = _make_command()
    mock_exec.get_commands.return_value = [_make_command()]
    mock_exec.get_actuator_states.return_value = [_make_actuator_state()]

    mock_alert_svc.get_alerts.return_value = [_make_alert()]
    mock_alert_svc.get_alert_summary.return_value = {
        "total": 5, "unresolved": 2, "critical_unresolved": 0, "resolved": 3,
    }
    mock_alert_svc.resolve_alert.return_value = True
    mock_alert_svc.resolve_device_alerts.return_value = 3

    mock_ag.get_messages.return_value = [
        {
            "id": "msg-00001",
            "sender": "data_agent",
            "target": "decision_agent",
            "type": "evaluate",
            "data": {"device_id": "room-1-sensor-temp"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]
    mock_ag.get_stats.return_value = {
        "readings_processed": 50,
        "messages_in_bus": 100,
        "engine": {
            "strategies": ["threshold", "no_motion_timeout", "anomaly_detection"],
            "total_decisions": 10,
        },
        "agent_performance": {},
    }
    mock_ag.engine.strategies = []

    mock_eq.get_stats.return_value = {"total_alerts": 5, "total_events": 50}

    mock_heartbeat = MagicMock()
    mock_heartbeat.get_stats.return_value = {
        "total_devices": 2, "online": 2, "offline": 0,
        "heartbeat_timeout_s": 60,
    }
    mock_heartbeat.get_offline_devices.return_value = []
    mock_heartbeat.get_online_devices.return_value = [
        {"device_id": "room-1-sensor-temp", "last_seen": datetime.now(timezone.utc).isoformat()},
        {"device_id": "room-1-actuator-fan", "last_seen": datetime.now(timezone.utc).isoformat()},
    ]

    mock_auth = MagicMock()
    mock_auth.get_stats.return_value = {
        "total_keys": 3, "active_keys": 2, "requests_by_key": {},
    }

    with (
        patch(PATCH_INGESTION, mock_ing),
        patch(PATCH_EXECUTION, mock_exec),
        patch(PATCH_ALERT, mock_alert_svc),
        patch(PATCH_AGENTS, mock_ag),
        patch(PATCH_MQTT, mock_mqtt),
        patch(PATCH_EVENT_QUEUE, mock_eq),
        patch(PATCH_HEARTBEAT, mock_heartbeat),
        patch(PATCH_AUTH_SERVICE, mock_auth),
    ):
        yield {
            "ingestion": mock_ing,
            "execution": mock_exec,
            "alert": mock_alert_svc,
            "agents": mock_ag,
            "event_queue": mock_eq,
            "heartbeat": mock_heartbeat,
            "auth": mock_auth,
        }


@pytest.fixture(scope="module")
def client():
    """Create TestClient once per module."""
    with (
        patch("app.core.database.engine", MagicMock()),
        patch("app.core.database.SessionLocal", MagicMock()),
    ):
        from app.main import app
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c


# ═══════════════════════════════════════════════════════════════
# Health & System Endpoints
# ═══════════════════════════════════════════════════════════════

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestInfoEndpoint:
    def test_info_returns_200(self, client):
        r = client.get("/api/v1/info")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "EdgeBrain"
        assert "version" in data


class TestStatsEndpoint:
    def test_stats_returns_200(self, client):
        r = client.get("/api/v1/stats")
        assert r.status_code == 200
        data = r.json()
        assert "alerts" in data
        assert "devices" in data


# ═══════════════════════════════════════════════════════════════
# Device Endpoints
# ═══════════════════════════════════════════════════════════════

class TestDeviceEndpoints:
    def test_get_devices(self, client):
        r = client.get("/api/v1/devices")
        assert r.status_code == 200
        devices = r.json()
        assert "devices" in devices
        assert isinstance(devices["devices"], list)
        assert len(devices["devices"]) >= 1
        assert "device_id" in devices["devices"][0]

    def test_get_device_found(self, client, mock_services):
        mock_services["ingestion"].get_device.return_value = _make_device_state("room-1-sensor-temp", "temperature")
        r = client.get("/api/v1/devices/room-1-sensor-temp")
        assert r.status_code == 200
        assert r.json()["device_id"] == "room-1-sensor-temp"

    def test_get_device_not_found(self, client, mock_services):
        mock_services["ingestion"].get_device.return_value = None
        r = client.get("/api/v1/devices/nonexistent-device")
        assert r.status_code == 404

    def test_get_device_readings(self, client):
        r = client.get("/api/v1/devices/room-1-sensor-temp/readings")
        assert r.status_code == 200
        assert "readings" in r.json()

    def test_get_device_readings_with_params(self, client, mock_services):
        r = client.get("/api/v1/devices/room-1-sensor-temp/readings?minutes=30&limit=100")
        assert r.status_code == 200
        mock_services["ingestion"].get_recent_readings.assert_called()

    def test_get_device_statistics(self, client):
        r = client.get("/api/v1/devices/room-1-sensor-temp/statistics")
        assert r.status_code == 200
        stats = r.json()
        assert stats["count"] == 100
        assert stats["avg"] == 25.5

    def test_get_device_statistics_no_data(self, client, mock_services):
        mock_services["ingestion"].get_statistics.return_value = {
            "device_id": "empty", "period_minutes": 60,
            "count": 0, "avg": None, "min": None, "max": None, "stddev": None,
        }
        r = client.get("/api/v1/devices/empty/statistics")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════
# Prediction Endpoint
# ═══════════════════════════════════════════════════════════════

class TestPredictionEndpoint:
    def test_predict_insufficient_data(self, client, mock_services):
        mock_services["ingestion"].get_recent_readings.return_value = [
            _make_reading(value=25.0) for _ in range(5)
        ]
        r = client.get("/api/v1/devices/room-1-sensor-temp/predict")
        assert r.status_code == 400

    def test_predict_success(self, client, mock_services):
        readings = [_make_reading(value=25.0 + i * 0.5) for i in range(30)]
        mock_services["ingestion"].get_recent_readings.return_value = readings
        r = client.get("/api/v1/devices/room-1-sensor-temp/predict")
        assert r.status_code == 200
        data = r.json()
        assert "predictions" in data
        assert "anomaly_score" in data

    def test_predict_with_steps(self, client, mock_services):
        readings = [_make_reading(value=25.0 + i * 0.5) for i in range(30)]
        mock_services["ingestion"].get_recent_readings.return_value = readings
        r = client.get("/api/v1/devices/room-1-sensor-temp/predict?steps=5")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════
# Export Endpoint
# ═══════════════════════════════════════════════════════════════

class TestExportEndpoint:
    def test_export_json(self, client, mock_services):
        r = client.get("/api/v1/devices/room-1-sensor-temp/export?format=json")
        assert r.status_code == 200
        assert "application/json" in r.headers["content-type"]

    def test_export_csv(self, client, mock_services):
        r = client.get("/api/v1/devices/room-1-sensor-temp/export?format=csv")
        assert r.status_code == 200
        assert "text/csv" in r.headers["content-type"]

    def test_export_invalid_format(self, client):
        r = client.get("/api/v1/devices/room-1-sensor-temp/export?format=xml")
        assert r.status_code == 422

    def test_export_no_data(self, client, mock_services):
        mock_services["ingestion"].get_recent_readings.return_value = []
        r = client.get("/api/v1/devices/nonexistent/export")
        assert r.status_code == 200
        assert r.json()["count"] == 0


# ═══════════════════════════════════════════════════════════════
# Readings Endpoint
# ═══════════════════════════════════════════════════════════════

class TestReadingsEndpoint:
    def test_get_all_readings(self, client):
        r = client.get("/api/v1/readings")
        assert r.status_code == 200
        assert "readings" in r.json()

    def test_get_readings_filtered(self, client):
        r = client.get("/api/v1/readings?device_type=temperature&minutes=30")
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════
# Command Endpoints
# ═══════════════════════════════════════════════════════════════

class TestCommandEndpoints:
    def test_send_command(self, client, mock_services):
        r = client.post("/api/v1/devices/room-1-actuator-fan/command?command=activate&params=%7B%22actuator%22%3A%20%22fan%22%7D")
        assert r.status_code == 200
        assert r.json()["status"] == "sent"

    def test_send_command_failure(self, client, mock_services):
        mock_services["execution"].send_command.return_value = None
        r = client.post("/api/v1/devices/room-1-actuator-fan/command?command=activate")
        assert r.status_code == 500

    def test_get_commands(self, client):
        r = client.get("/api/v1/commands")
        assert r.status_code == 200
        assert "commands" in r.json()

    def test_get_commands_filtered(self, client):
        r = client.get("/api/v1/commands?device_id=room-1-actuator-fan&limit=10")
        assert r.status_code == 200

    def test_get_actuators(self, client):
        r = client.get("/api/v1/actuators")
        assert r.status_code == 200
        assert "actuators" in r.json()


# ═══════════════════════════════════════════════════════════════
# Alert Endpoints
# ═══════════════════════════════════════════════════════════════

class TestAlertEndpoints:
    def test_get_alerts(self, client):
        r = client.get("/api/v1/alerts")
        assert r.status_code == 200
        assert "alerts" in r.json()

    def test_get_alerts_with_filters(self, client):
        r = client.get("/api/v1/alerts?unresolved_only=true&severity=warning&limit=10")
        assert r.status_code == 200

    def test_resolve_alert(self, client):
        r = client.post("/api/v1/alerts/alert-001/resolve")
        assert r.status_code == 200

    def test_resolve_alert_not_found(self, client, mock_services):
        mock_services["alert"].resolve_alert.return_value = False
        r = client.post("/api/v1/alerts/nonexistent/resolve")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════
# Agent Endpoints
# ═══════════════════════════════════════════════════════════════

class TestAgentEndpoints:
    def test_get_agent_messages(self, client):
        r = client.get("/api/v1/agents/messages")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_agent_messages_filtered(self, client):
        r = client.get("/api/v1/agents/messages?agent=data_agent&limit=10")
        assert r.status_code == 200

    def test_get_agent_stats(self, client):
        r = client.get("/api/v1/agents/stats")
        assert r.status_code == 200
        data = r.json()
        assert "readings_processed" in data
        assert "engine" in data

    def test_get_strategies(self, client):
        r = client.get("/api/v1/agents/strategies")
        assert r.status_code == 200
        assert "strategies" in r.json()


# ═══════════════════════════════════════════════════════════════
# Validation & Edge Cases
# ═══════════════════════════════════════════════════════════════

class TestValidation:
    def test_command_missing_fields(self, client):
        r = client.post("/api/v1/devices/test/command", json={})
        assert r.status_code == 422

    def test_readings_invalid_minutes(self, client):
        r = client.get("/api/v1/readings?minutes=0")
        assert r.status_code == 422

    def test_readings_excessive_limit(self, client):
        r = client.get("/api/v1/readings?limit=99999")
        assert r.status_code == 422

    def test_predict_invalid_steps(self, client):
        r = client.get("/api/v1/devices/test/predict?steps=0")
        assert r.status_code == 422

    def test_export_invalid_minutes(self, client):
        r = client.get("/api/v1/devices/test/export?minutes=0")
        assert r.status_code == 422
