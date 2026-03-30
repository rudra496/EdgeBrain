import json
import logging
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.agents.multi_agent import agents
from app.services.ingestion import data_ingestion
from app.services.execution import AlertService
from app.core.mqtt_client import mqtt_client
from app.core.events import event_queue

logger = logging.getLogger(__name__)
router = APIRouter()
alert_service = AlertService()


def on_mqtt_message(topic: str, payload: dict):
    """Handle incoming MQTT sensor data."""
    device_id = payload.get("device_id", "unknown")
    device_type = payload.get("device_type", "unknown")
    value = payload.get("value", 0)
    unit = payload.get("unit", "")
    extra = payload.get("extra", {})

    agents.data_agent(device_id, device_type, value, unit, extra)


mqtt_client.subscribe("device/+/data", on_mqtt_message)


@router.get("/devices")
def get_devices():
    return data_ingestion.get_all_device_states()


@router.get("/devices/{device_id}/readings")
def get_readings(device_id: str, minutes: int = 60, limit: int = 500):
    return data_ingestion.get_recent_readings(device_id, minutes, limit)


@router.get("/alerts")
def get_alerts(limit: int = 50, unresolved_only: bool = False):
    return alert_service.get_alerts(limit, unresolved_only)


@router.get("/agents/messages")
def get_agent_messages(limit: int = 50):
    return agents.get_messages(limit)


@router.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        self.active.remove(ws)

    async def broadcast(self, data: dict):
        msg = json.dumps(data)
        for ws in self.active[:]:
            try:
                await ws.send_text(msg)
            except Exception:
                self.active.remove(ws)


ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send initial data
        await ws.send_text(json.dumps({
            "type": "init",
            "devices": data_ingestion.get_all_device_states(),
            "alerts": alert_service.get_alerts(limit=20),
        }))
        while True:
            # Keep alive, receive commands from dashboard
            data = await ws.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "command":
                    device_id = msg["device_id"]
                    command = msg["command"]
                    params = msg.get("params", {})
                    from app.services.execution import ExecutionService
                    exec_svc = ExecutionService(mqtt_client)
                    exec_svc.send_command(device_id, command, params, source="dashboard")
                    await ws_manager.broadcast({"type": "command_sent", "device_id": device_id, "command": command})
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
        logger.info("Dashboard disconnected")
