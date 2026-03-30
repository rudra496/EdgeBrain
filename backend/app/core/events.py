import logging
import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def get_redis() -> redis.Redis:
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


class EventQueue:
    def __init__(self):
        self.redis = get_redis()

    def push(self, event: dict):
        self.redis.rpush("edgebrain:events", str(event))
        logger.info(f"Event queued: {event.get('type', 'unknown')}")

    def pop(self) -> dict | None:
        result = self.redis.lpop("edgebrain:events")
        return eval(result) if result else None

    def push_alert(self, alert: dict):
        self.redis.rpush("edgebrain:alerts", str(alert))
        self.redis.publish("edgebrain:alerts:live", str(alert))

    def get_alerts(self, limit: int = 50) -> list[dict]:
        alerts = self.redis.lrange("edgebrain:alerts", -limit, -1)
        return [eval(a) for a in alerts]


event_queue = EventQueue()
