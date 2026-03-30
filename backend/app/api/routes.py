"""EdgeBrain API — REST endpoints + WebSocket handler.

Endpoints:
  /health              — System health check
  /info                — System information
  /stats               — Comprehensive statistics
  /devices             — All device states
  /devices/{id}        — Single device state
  /devices/{id}/readings — Historical readings
  /devices/{id}/statistics — Statistical summary
  /devices/{id}/predict — AI prediction
  /devices/{id}/export — Data export (CSV/JSON)
  /devices/{id}/command — Send command
  /readings            — All readings (filterable)
  /actuators           — Actuator states
  /commands            — Command history
  /alerts              — Alert log
  /alerts/summary      — Alert counts
  /alerts/{id}/resolve — Resolve alert
  /agents/messages     — Agent message log
  /agents/stats        — Agent performance
  /agents/strategies   — Registered strategies
  /ws                  — WebSocket (real-time)
"""
import asyncio
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query, Response
from fastapi.responses import StreamingResponse

from app.agents.multi_agent import agents
from app.services.ingestion import data_ingestion
from app.services.execution import execution_service, alert_service
from app.core.mqtt_client import mqtt_client
from app.core.events import event_queue
from app.ai.prediction import predictor
from app.api.schemas import (
    CommandIn, MessageResponse, HealthCheck, SystemStats, SystemInfo,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── MQTT Bridge ────────────────────────────────────────────

def on_mqtt_message(topic: str, payload: dict):
    """Bridge: MQTT → Agent Pipeline → WebSocket broadcast."""
    device_id = payload.get("device_id", "unknown")
    device_type = payload.get("device_type", "unknown")
    value = payload.get("value", 0)
    unit = payload.get("unit", "")
    extra = payload.get("extra", {})
    room = payload.get("room", "")

    agents.data_agent(device_id, device_type, float(value), unit, extra)

    broadcast_to_all({
        "type": "sensor_data",
        "device_id": device_id,
        "device_type": device_type,
        "value": float(value),
        "unit": unit,
        "room": room,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


mqtt_client.subscribe_all(on_mqtt_message)


# ─── WebSocket Manager ─────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.append(ws)
        logger.info(f"WS connected ({len(self.active)} total)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)

    async def broadcast(self, data: dict):
        if not self.active:
            return
        msg = json.dumps(data, default=str)
        dead = []
        async with self._lock:
            for ws in self.active:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active.remove(ws)

    @property
    def count(self) -> int:
        return len(self.active)


ws_manager = ConnectionManager()


def broadcast_to_all(data: dict):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast(data))
    except RuntimeError:
        pass


# ═══════════════════════════════════════════════════════════════
# REST ENDPOINTS
# ═══════════════════════════════════════════════════════════════

# ─── Health & Info ────────────────────────────────────────

@router.get("/health", response_model=HealthCheck)
def health():
    return HealthCheck(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        mqtt_connected=mqtt_client.is_connected,
    )


@router.get("/info", response_model=SystemInfo)
def system_info():
    return SystemInfo(
        name="EdgeBrain",
        version="1.0.0",
        components={
            "backend": "FastAPI + SQLAlchemy",
            "database": "PostgreSQL 16",
            "cache": "Redis 7",
            "messaging": "MQTT (Mosquitto)",
            "ai_engine": "Rules + Anomaly Detection + Prediction",
            "agents": ["Data Agent", "Decision Agent", "Action Agent"],
            "simulator": "11 devices across 3 rooms",
        },
        mqtt_status="connected" if mqtt_client.is_connected else "disconnected",
    )


@router.get("/stats", response_model=SystemStats)
def system_stats():
    return SystemStats(
        alerts=alert_service.get_alert_summary(),
        agents=agents.get_stats(),
        ingestion=data_ingestion.get_ingestion_stats(),
        events=event_queue.get_stats(),
        mqtt_connected=mqtt_client.is_connected,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


# ─── Device Endpoints ─────────────────────────────────────

@router.get("/devices")
def get_devices():
    return data_ingestion.get_all_device_states()


@router.get("/devices/{device_id}")
def get_device(device_id: str):
    for d in data_ingestion.get_all_device_states():
        if d["device_id"] == device_id:
            return d
    raise HTTPException(404, f"Device '{device_id}' not found")


@router.get("/devices/{device_id}/readings")
def get_device_readings(
    device_id: str,
    minutes: int = Query(default=60, ge=1, le=10080),
    limit: int = Query(default=500, ge=1, le=10000),
):
    return data_ingestion.get_recent_readings(device_id, minutes, limit)


@router.get("/devices/{device_id}/statistics")
def get_device_statistics(device_id: str, minutes: int = Query(default=60, ge=1, le=10080)):
    stats = data_ingestion.get_statistics(device_id, minutes)
    if stats["count"] == 0:
        raise HTTPException(404, f"No data for '{device_id}' in last {minutes} minutes")
    return stats


@router.get("/devices/{device_id}/predict")
def predict_device(device_id: str, steps: int = Query(default=5, ge=1, le=50)):
    """AI prediction for a device's next values."""
    readings = data_ingestion.get_recent_readings(device_id, minutes=60, limit=200)
    if len(readings) < 10:
        raise HTTPException(400, f"Not enough data for prediction ({len(readings)} readings)")

    values = [r["value"] for r in readings]
    predictions = predictor.predict(values, steps)
    anomaly_score = predictor.get_anomaly_score(values, values[-1])
    moving_avgs = predictor.get_moving_averages(values)

    return {
        "device_id": device_id,
        "current_value": values[-1],
        "anomaly_score": anomaly_score,
        "predictions": [
            {
                "value": p.value,
                "confidence": p.confidence,
                "method": p.method,
                "horizon": p.horizon,
                "details": p.details,
            }
            for p in predictions
        ],
        "moving_averages": {k: [round(v, 2) for v in vals] for k, vals in moving_avgs.items()},
        "data_points_used": len(values),
    }


@router.get("/devices/{device_id}/export")
def export_device_data(
    device_id: str,
    format: str = Query(default="json", regex="^(json|csv)$"),
    minutes: int = Query(default=1440, ge=1, le=10080),
    limit: int = Query(default=10000, ge=1, le=100000),
):
    """Export device readings as CSV or JSON."""
    readings = data_ingestion.get_recent_readings(device_id, minutes, limit)
    if not readings:
        raise HTTPException(404, f"No data for '{device_id}'")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

    if format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["timestamp", "device_id", "device_type", "value", "unit"])
        writer.writeheader()
        for r in readings:
            writer.writerow({
                "timestamp": r["timestamp"],
                "device_id": r["device_id"],
                "device_type": r["device_type"],
                "value": r["value"],
                "unit": r["unit"],
            })
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=edgebrain_{device_id}_{timestamp}.csv"},
        )
    else:
        return StreamingResponse(
            iter([json.dumps(readings, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=edgebrain_{device_id}_{timestamp}.json"},
        )


@router.get("/readings")
def get_all_readings(
    device_type: Optional[str] = None,
    minutes: int = Query(default=60, ge=1, le=10080),
    limit: int = Query(default=200, ge=1, le=5000),
):
    return data_ingestion.get_all_readings(device_type, minutes, limit)


# ─── Command Endpoints ────────────────────────────────────

@router.post("/devices/{device_id}/command")
def send_command(device_id: str, cmd: CommandIn):
    result = execution_service.send_command(
        device_id=device_id,
        command=cmd.command,
        params=cmd.params,
        source="api",
    )
    if result is None:
        raise HTTPException(500, "Command failed to send")
    return result


@router.get("/commands")
def get_commands(device_id: Optional[str] = None, limit: int = Query(default=50, ge=1, le=500)):
    return execution_service.get_commands(device_id, limit)


@router.get("/actuators")
def get_actuator_states():
    return execution_service.get_actuator_states()


# ─── Alert Endpoints ──────────────────────────────────────

@router.get("/alerts")
def get_alerts(
    limit: int = Query(default=50, ge=1, le=500),
    unresolved_only: bool = False,
    device_id: Optional[str] = None,
    severity: Optional[str] = None,
):
    return alert_service.get_alerts(limit, unresolved_only, device_id, severity)


@router.get("/alerts/summary")
def get_alert_summary():
    return alert_service.get_alert_summary()


@router.post("/alerts/{alert_id}/resolve", response_model=MessageResponse)
def resolve_alert(alert_id: str):
    if alert_service.resolve_alert(alert_id):
        return MessageResponse(message="resolved", detail=f"Alert {alert_id} resolved")
    raise HTTPException(404, "Alert not found")


@router.post("/devices/{device_id}/resolve-alerts", response_model=MessageResponse)
def resolve_device_alerts(device_id: str):
    count = alert_service.resolve_device_alerts(device_id)
    return MessageResponse(message="resolved", detail=f"{count} alerts resolved for {device_id}")


# ─── Agent Endpoints ──────────────────────────────────────

@router.get("/agents/messages")
def get_agent_messages(
    limit: int = Query(default=50, ge=1, le=200),
    agent: Optional[str] = None,
):
    return agents.get_messages(limit, agent)


@router.get("/agents/stats")
def get_agent_stats():
    return agents.get_stats()


@router.get("/agents/strategies")
def get_strategies():
    return {
        "strategies": [
            {"name": s.name, "type": s.__class__.__name__}
            for s in agents.engine.strategies
        ]
    }


# ═══════════════════════════════════════════════════════════════
# WEBSOCKET
# ═══════════════════════════════════════════════════════════════

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    Real-time WebSocket connection.

    Auto-receives:
    - init (device states, alerts, actuators)
    - sensor_data (live readings)
    - command_sent (actuator commands)
    - alerts_resolved (bulk resolve)

    Can send:
    - {"type": "command", "device_id": "...", "command": "...", "params": {}}
    - {"type": "resolve_alert", "alert_id": "..."}
    - {"type": "resolve_alert", "device_id": "..."}
    - {"type": "ping"}
    """
    await ws_manager.connect(ws)
    try:
        await ws.send_text(json.dumps({
            "type": "init",
            "devices": data_ingestion.get_all_device_states(),
            "alerts": alert_service.get_alerts(limit=20),
            "actuators": execution_service.get_actuator_states(),
            "stats": system_stats().model_dump(),
            "ws_clients": ws_manager.count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "command":
                    result = execution_service.send_command(
                        device_id=msg["device_id"],
                        command=msg["command"],
                        params=msg.get("params", {}),
                        source="dashboard",
                    )
                    await ws_manager.broadcast({
                        "type": "command_sent",
                        "device_id": msg["device_id"],
                        "command": msg["command"],
                        "params": msg.get("params", {}),
                        "success": result is not None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif msg_type == "resolve_alert":
                    alert_id = msg.get("alert_id")
                    device_id = msg.get("device_id")
                    if alert_id:
                        alert_service.resolve_alert(alert_id)
                        await ws_manager.broadcast({"type": "alert_resolved", "alert_id": alert_id})
                    elif device_id:
                        count = alert_service.resolve_device_alerts(device_id)
                        await ws_manager.broadcast({
                            "type": "alerts_resolved",
                            "device_id": device_id,
                            "count": count,
                        })

                elif msg_type == "ping":
                    await ws.send_text(json.dumps({
                        "type": "pong",
                        "ws_clients": ws_manager.count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
