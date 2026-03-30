import json
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.responses import StreamingResponse
from app.agents.multi_agent import agents
from app.services.ingestion import data_ingestion
from app.services.execution import execution_service, alert_service
from app.core.mqtt_client import mqtt_client
from app.core.events import event_queue

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── MQTT Bridge ────────────────────────────────────────────

def on_mqtt_message(topic: str, payload: dict):
    """Bridge MQTT messages into the agent pipeline."""
    device_id = payload.get("device_id", "unknown")
    device_type = payload.get("device_type", "unknown")
    value = payload.get("value", 0)
    unit = payload.get("unit", "")
    extra = payload.get("extra", {})

    agents.data_agent(device_id, device_type, float(value), unit, extra)

    # Broadcast to all WebSocket clients
    broadcast_to_all({
        "type": "sensor_data",
        "device_id": device_id,
        "device_type": device_type,
        "value": float(value),
        "unit": unit,
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
        logger.info(f"WebSocket connected ({len(self.active)} total)")

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            if ws in self.active:
                self.active.remove(ws)
        logger.info(f"WebSocket disconnected ({len(self.active)} total)")

    async def broadcast(self, data: dict):
        if not self.active:
            return
        msg = json.dumps(data)
        dead = []
        async with self._lock:
            for ws in self.active:
                try:
                    await ws.send_text(msg)
                except Exception:
                    dead.append(ws)
            for ws in dead:
                self.active.remove(ws)


ws_manager = ConnectionManager()


def broadcast_to_all(data: dict):
    """Thread-safe broadcast from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(ws_manager.broadcast(data))
    except RuntimeError:
        pass  # No event loop yet


# ─── REST Endpoints ────────────────────────────────────────

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mqtt_connected": mqtt_client.is_connected,
    }


# ─── Device Endpoints ──────────────────────────────────────

@router.get("/devices")
def get_devices():
    """Get all device states."""
    return data_ingestion.get_all_device_states()


@router.get("/devices/{device_id}")
def get_device(device_id: str):
    """Get specific device state."""
    devices = data_ingestion.get_all_device_states()
    for d in devices:
        if d["device_id"] == device_id:
            return d
    raise HTTPException(404, f"Device {device_id} not found")


@router.get("/devices/{device_id}/readings")
def get_device_readings(device_id: str, minutes: int = 60, limit: int = 500):
    """Get historical readings for a device."""
    return data_ingestion.get_recent_readings(device_id, minutes, limit)


@router.get("/devices/{device_id}/statistics")
def get_device_statistics(device_id: str, minutes: int = 60):
    """Get statistical summary for a device."""
    stats = data_ingestion.get_statistics(device_id, minutes)
    if stats["count"] == 0:
        raise HTTPException(404, f"No data for {device_id} in last {minutes} minutes")
    return stats


@router.get("/readings")
def get_all_readings(device_type: Optional[str] = None, minutes: int = 60, limit: int = 200):
    """Get all readings, optionally filtered by device type."""
    return data_ingestion.get_all_readings(device_type, minutes, limit)


# ─── Command Endpoints ─────────────────────────────────────

@router.post("/devices/{device_id}/command")
def send_command(device_id: str, command: str, params: dict = None):
    """Manually send a command to a device."""
    result = execution_service.send_command(
        device_id=device_id,
        command=command,
        params=params or {},
        source="api",
    )
    if result is None:
        raise HTTPException(500, "Command failed to send")
    return result


@router.get("/commands")
def get_commands(device_id: Optional[str] = None, limit: int = 50):
    """Get command history."""
    return execution_service.get_commands(device_id, limit)


@router.get("/actuators")
def get_actuator_states():
    """Get all actuator states."""
    return execution_service.get_actuator_states()


# ─── Alert Endpoints ───────────────────────────────────────

@router.get("/alerts")
def get_alerts(
    limit: int = 50,
    unresolved_only: bool = False,
    device_id: Optional[str] = None,
    severity: Optional[str] = None,
):
    """Get alerts with optional filters."""
    return alert_service.get_alerts(limit, unresolved_only, device_id, severity)


@router.get("/alerts/summary")
def get_alert_summary():
    """Get alert counts by severity."""
    return alert_service.get_alert_summary()


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    """Resolve a specific alert."""
    if alert_service.resolve_alert(alert_id):
        return {"status": "resolved", "alert_id": alert_id}
    raise HTTPException(404, "Alert not found")


@router.post("/devices/{device_id}/resolve-alerts")
def resolve_device_alerts(device_id: str):
    """Resolve all unresolved alerts for a device."""
    count = alert_service.resolve_device_alerts(device_id)
    return {"resolved": count, "device_id": device_id}


# ─── Agent Endpoints ───────────────────────────────────────

@router.get("/agents/messages")
def get_agent_messages(limit: int = 50, agent: Optional[str] = None):
    """Get internal agent communication messages."""
    return agents.get_messages(limit, agent)


@router.get("/agents/stats")
def get_agent_stats():
    """Get agent system performance statistics."""
    return agents.get_stats()


@router.get("/agents/strategies")
def get_strategies():
    """Get registered decision strategies."""
    return {
        "strategies": [
            {"name": s.name, "type": s.__class__.__name__}
            for s in agents.engine.strategies
        ]
    }


# ─── System Endpoints ──────────────────────────────────────

@router.get("/stats")
def get_system_stats():
    """Comprehensive system statistics."""
    return {
        "alerts": alert_service.get_alert_summary(),
        "agents": agents.get_stats(),
        "ingestion": data_ingestion.get_ingestion_stats(),
        "events": event_queue.get_stats(),
        "mqtt_connected": mqtt_client.is_connected,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ─── WebSocket ─────────────────────────────────────────────

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Real-time WebSocket connection for dashboard.

    Receives:
    - Initial state dump (devices, alerts, actuators)
    - Live sensor data broadcasts
    - Live alert broadcasts
    - Live command broadcasts

    Sends:
    - Manual commands: {"type": "command", "device_id": "...", "command": "...", "params": {}}
    """
    await ws_manager.connect(ws)
    try:
        # Send initial state
        await ws.send_text(json.dumps({
            "type": "init",
            "devices": data_ingestion.get_all_device_states(),
            "alerts": alert_service.get_alerts(limit=20),
            "actuators": execution_service.get_actuator_states(),
            "stats": get_system_stats(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }))

        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)

                if msg.get("type") == "command":
                    device_id = msg["device_id"]
                    command = msg["command"]
                    params = msg.get("params", {})

                    result = execution_service.send_command(
                        device_id=device_id,
                        command=command,
                        params=params,
                        source="dashboard",
                    )

                    await ws_manager.broadcast({
                        "type": "command_sent",
                        "device_id": device_id,
                        "command": command,
                        "params": params,
                        "success": result is not None,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif msg.get("type") == "resolve_alert":
                    alert_id = msg.get("alert_id")
                    device_id = msg.get("device_id")
                    if alert_id:
                        alert_service.resolve_alert(alert_id)
                    elif device_id:
                        count = alert_service.resolve_device_alerts(device_id)
                        await ws_manager.broadcast({
                            "type": "alerts_resolved",
                            "device_id": device_id,
                            "count": count,
                        })

                elif msg.get("type") == "ping":
                    await ws.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }))

            except json.JSONDecodeError:
                logger.warning("Invalid WebSocket message received")
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(ws)
