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
  /alerts/{id}/acknowledge — Acknowledge alert
  /alerts/{id}/resolve — Resolve alert
  /heartbeat           — Device heartbeat status
  /metrics             — Prometheus metrics
  /ws                  — WebSocket real-time feed
"""

import asyncio
import csv
import io
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse, Response

from app.core.auth import verify_api_key, verify_write_access, verify_admin_access, auth_service
from app.core.heartbeat import device_heartbeat
from app.core.metrics import get_metrics, get_metrics_content_type
from app.services.ingestion import data_ingestion
from app.services.execution import execution_service, alert_service
from app.ai.prediction import predictor
from app.agents.multi_agent import agents

logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════════════════
# Health and Info
# ═══════════════════════════════════════════════════════════


@router.get("/stats")
def get_stats(key_info: dict = Depends(verify_api_key)):
    """Comprehensive system statistics."""
    device_stats = data_ingestion.get_device_summary()
    ingestion_stats = data_ingestion.get_ingestion_stats()
    heartbeat_stats = device_heartbeat.get_stats()
    alert_stats = alert_service.get_stats()
    auth_stats = auth_service.get_stats()

    return {
        "devices": device_stats,
        "heartbeat": heartbeat_stats,
        "ingestion": ingestion_stats,
        "alerts": alert_stats,
        "auth": auth_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ═══════════════════════════════════════════════════════════
# Devices
# ═══════════════════════════════════════════════════════════


@router.get("/devices")
def get_devices(key_info: dict = Depends(verify_api_key)):
    """Get all device states."""
    devices = data_ingestion.get_all_devices()
    for device in devices:
        device_id = device["device_id"]
        device["heartbeat_online"] = device_heartbeat.is_online(device_id)
        device["last_seen_heartbeat"] = (
            device_heartbeat.get_last_seen(device_id).isoformat()
            if device_heartbeat.get_last_seen(device_id)
            else None
        )
    return {"count": len(devices), "devices": devices}


@router.get("/devices/{device_id}")
def get_device(device_id: str, key_info: dict = Depends(verify_api_key)):
    """Get single device state."""
    device = data_ingestion.get_device(device_id)
    if not device:
        raise HTTPException(404, f"Device '{device_id}' not found")
    device["heartbeat_online"] = device_heartbeat.is_online(device_id)
    device["last_seen_heartbeat"] = (
        device_heartbeat.get_last_seen(device_id).isoformat()
        if device_heartbeat.get_last_seen(device_id)
        else None
    )
    return device


@router.get("/devices/{device_id}/readings")
def get_device_readings(
    device_id: str,
    minutes: int = Query(default=60, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=10000),
    key_info: dict = Depends(verify_api_key),
):
    """Get historical readings for a device."""
    readings = data_ingestion.get_recent_readings(device_id, minutes, limit)
    return {"device_id": device_id, "count": len(readings), "readings": readings}


@router.get("/devices/{device_id}/statistics")
def get_device_statistics(
    device_id: str,
    minutes: int = Query(default=60, ge=1, le=10080),
    key_info: dict = Depends(verify_api_key),
):
    """Get statistical summary for a device."""
    stats = data_ingestion.get_statistics(device_id, minutes)
    if stats["count"] == 0:
        raise HTTPException(404, f"No data for '{device_id}' in last {minutes} minutes")
    return stats


@router.get("/devices/{device_id}/predict")
def predict_device(
    device_id: str,
    steps: int = Query(default=5, ge=1, le=50),
    key_info: dict = Depends(verify_api_key),
):
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
        "predictions": predictions,
        "moving_averages": moving_avgs,
    }


@router.get("/devices/{device_id}/export")
def export_device_data(
    device_id: str,
    format: str = Query(default="json", pattern="^(json|csv)$"),
    minutes: int = Query(default=1440, ge=1, le=10080),
    key_info: dict = Depends(verify_api_key),
):
    """Export device data as JSON or CSV."""
    readings = data_ingestion.get_recent_readings(device_id, minutes, limit=10000)

    if format == "csv":
        output = io.StringIO()
        if readings:
            writer = csv.DictWriter(output, fieldnames=readings[0].keys())
            writer.writeheader()
            writer.writerows(readings)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode()),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={device_id}.csv"},
        )

    return {"device_id": device_id, "count": len(readings), "readings": readings}


@router.post("/devices/{device_id}/command")
def send_device_command(
    device_id: str,
    command: str = Query(...),
    params: Optional[str] = Query(default=None),
    source: str = Query(default="api"),
    key_info: dict = Depends(verify_write_access),
):
    """Send command to a device."""
    parsed_params = {}
    if params:
        try:
            parsed_params = json.loads(params)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON in params")

    result = execution_service.send_command(device_id, command, parsed_params, source)
    if not result:
        raise HTTPException(500, "Failed to send command")
    return result


# ═══════════════════════════════════════════════════════════
# Readings
# ═══════════════════════════════════════════════════════════


@router.get("/readings")
def get_readings(
    device_type: Optional[str] = None,
    minutes: int = Query(default=60, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=10000),
    key_info: dict = Depends(verify_api_key),
):
    """Get all readings (filterable)."""
    readings = data_ingestion.get_all_readings(device_type, minutes, limit)
    return {"count": len(readings), "readings": readings}


# ═══════════════════════════════════════════════════════════
# Actuators
# ═══════════════════════════════════════════════════════════


@router.get("/actuators")
def get_actuators(key_info: dict = Depends(verify_api_key)):
    """Get all actuator states."""
    actuators = data_ingestion.get_all_actuators()
    return {"count": len(actuators), "actuators": actuators}


# ═══════════════════════════════════════════════════════════
# Commands
# ═══════════════════════════════════════════════════════════


@router.get("/commands")
def get_commands(
    minutes: int = Query(default=60, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=10000),
    key_info: dict = Depends(verify_api_key),
):
    """Get command history."""
    commands = execution_service.get_commands(minutes, limit)
    return {"count": len(commands), "commands": commands}


# ═══════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════


@router.get("/alerts")
def get_alerts(
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    minutes: int = Query(default=1440, ge=1, le=10080),
    limit: int = Query(default=100, ge=1, le=10000),
    key_info: dict = Depends(verify_api_key),
):
    """Get alert log."""
    alerts = alert_service.get_alerts(severity, resolved, minutes, limit)
    return {"count": len(alerts), "alerts": alerts}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(
    alert_id: str,
    acknowledged_by: str = Query(default="api_user"),
    key_info: dict = Depends(verify_write_access),
):
    """Acknowledge an alert."""
    result = alert_service.acknowledge_alert(alert_id, acknowledged_by)
    if not result:
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    return result


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(
    alert_id: str,
    resolved_by: str = Query(default="api_user"),
    resolution_note: Optional[str] = Query(default=None),
    key_info: dict = Depends(verify_write_access),
):
    """Resolve an alert."""
    result = alert_service.resolve_alert(alert_id, resolved_by, resolution_note)
    if not result:
        raise HTTPException(404, f"Alert '{alert_id}' not found")
    return result


# ═══════════════════════════════════════════════════════════
# Heartbeat
# ═══════════════════════════════════════════════════════════


@router.get("/heartbeat")
def get_heartbeat(key_info: dict = Depends(verify_api_key)):
    """Get device heartbeat status."""
    stats = device_heartbeat.get_stats()
    offline = device_heartbeat.get_offline_devices()
    online = device_heartbeat.get_online_devices()

    return {
        "total_devices": stats["total_devices"],
        "online": stats["online"],
        "offline": stats["offline"],
        "heartbeat_timeout_s": stats["heartbeat_timeout_s"],
        "online_devices": online,
        "offline_devices": offline,
    }


# ═══════════════════════════════════════════════════════════
# Metrics (Prometheus)
# ═══════════════════════════════════════════════════════════


@router.get("/metrics")
def get_prometheus_metrics():
    """Prometheus metrics endpoint (no auth required for scraping)."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


# ═══════════════════════════════════════════════════════════
# Auth Stats (Admin)
# ═══════════════════════════════════════════════════════════


@router.get("/auth/stats")
def get_auth_stats(key_info: dict = Depends(verify_admin_access)):
    """Get API key usage statistics (admin only)."""
    return auth_service.get_stats()


# ═══════════════════════════════════════════════════════════
# Agent Endpoints
# ═══════════════════════════════════════════════════════════


@router.get("/agents/messages")
def get_agent_messages(
    limit: int = Query(default=50, ge=1, le=200),
    agent: Optional[str] = None,
    key_info: dict = Depends(verify_api_key),
):
    """Get recent agent messages."""
    return agents.get_messages(limit, agent)


@router.get("/agents/stats")
def get_agent_stats(key_info: dict = Depends(verify_api_key)):
    """Get system-wide agent statistics."""
    return agents.get_stats()


@router.get("/agents/strategies")
def get_strategies(key_info: dict = Depends(verify_api_key)):
    """List loaded AI strategies."""
    return {
        "strategies": [
            {"name": s.name, "type": s.__class__.__name__}
            for s in agents.engine.strategies
        ]
    }


# ═══════════════════════════════════════════════════════════
# WebSocket
# ═══════════════════════════════════════════════════════════


class WebSocketManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self.active.append(ws)

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


ws_manager = WebSocketManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await ws_manager.connect(ws)
    try:
        # Send initial state
        await ws.send_text(json.dumps({
            "type": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                msg_type = msg.get("type", "")

                if msg_type == "ping":
                    await ws.send_text(json.dumps({"type": "pong"}))

                elif msg_type == "get_stats":
                    stats = data_ingestion.get_device_summary()
                    await ws.send_text(json.dumps({
                        "type": "stats",
                        "data": stats,
                    }))

            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
