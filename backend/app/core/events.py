import logging
import json
import redis
from datetime import datetime, timedelta
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

ALERTS_KEY = "edgebrain:alerts"
EVENTS_KEY = "edgebrain:events"
TELEMETRY_KEY = "edgebrain:telemetry"
MAX_ALERTS = 500
MAX_EVENTS = 5000


def get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


class EventQueue:
    """Redis-backed event queue with pub/sub for real-time notifications."""

    def __init__(self):
        self._redis: redis.Redis | None = None

    @property
    def redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = get_redis()
        return self._redis

    def push_event(self, event_type: str, data: dict):
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis.lpush(EVENTS_KEY, json.dumps(event))
        self.redis.ltrim(EVENTS_KEY, 0, MAX_EVENTS)
        self.redis.publish(f"edgebrain:events:{event_type}", json.dumps(event))
        logger.info(f"Event: {event_type}")

    def push_alert(self, alert: dict):
        alert["timestamp"] = alert.get("timestamp", datetime.utcnow().isoformat())
        self.redis.lpush(ALERTS_KEY, json.dumps(alert))
        self.redis.ltrim(ALERTS_KEY, 0, MAX_ALERTS)
        self.redis.publish("edgebrain:alerts:live", json.dumps(alert))
        logger.warning(f"Alert [{alert.get('severity')}] {alert.get('device_id')}: {alert.get('message')}")

    def push_telemetry(self, device_id: str, device_type: str, value: float, unit: str):
        telemetry = {
            "device_id": device_id,
            "device_type": device_type,
            "value": value,
            "unit": unit,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.redis.publish("edgebrain:telemetry:live", json.dumps(telemetry))

    def get_alerts(self, limit: int = 50) -> list[dict]:
        results = self.redis.lrange(ALERTS_KEY, 0, limit - 1)
        return [json.loads(r) for r in results]

    def get_events(self, limit: int = 100, event_type: str | None = None) -> list[dict]:
        results = self.redis.lrange(EVENTS_KEY, 0, limit - 1)
        events = [json.loads(r) for r in results]
        if event_type:
            events = [e for e in events if e.get("type") == event_type]
        return events

    def get_stats(self) -> dict:
        return {
            "total_alerts": self.redis.llen(ALERTS_KEY),
            "total_events": self.redis.llen(EVENTS_KEY),
        }

    def reset(self):
        self.redis.delete(ALERTS_KEY, EVENTS_KEY)
        logger.info("Event queues reset")


event_queue = EventQueue()
