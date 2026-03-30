import json
import logging
import threading
from typing import Callable
import paho.mqtt.client as mqtt
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MQTTClient:
    """Thread-safe MQTT client with wildcard support."""

    def __init__(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="edgebrain-backend",
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self._handlers: dict[str, list[Callable]] = {}
        self._wildcard_handlers: list[Callable] = []
        self._connected = False
        self._lock = threading.Lock()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info(f"MQTT connected (rc={reason_code})")
        with self._lock:
            self._connected = True
        # Re-subscribe on reconnect
        topics = list(self._handlers.keys()) + ["#"] if self._wildcard_handlers else list(self._handlers.keys())
        for t in topics:
            if t != "#":
                client.subscribe(t)

    def _on_disconnect(self, client, userdata, reason_code, properties=None):
        logger.warning(f"MQTT disconnected (rc={reason_code})")
        with self._lock:
            self._connected = False

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            # Topic-specific handlers
            for handler in self._handlers.get(topic, []):
                try:
                    handler(topic, payload)
                except Exception as e:
                    logger.error(f"Handler error on {topic}: {e}")
            # Wildcard handlers
            for handler in self._wildcard_handlers:
                try:
                    handler(topic, payload)
                except Exception as e:
                    logger.error(f"Wildcard handler error on {topic}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"MQTT payload decode error: {e}")
        except Exception as e:
            logger.error(f"MQTT message processing error: {e}")

    def connect(self):
        try:
            self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._connected

    def subscribe(self, topic: str, handler: Callable):
        with self._lock:
            if topic not in self._handlers:
                self._handlers[topic] = []
            self._handlers[topic].append(handler)
        if self._connected:
            self.client.subscribe(topic)
            logger.info(f"MQTT subscribed to {topic}")

    def subscribe_all(self, handler: Callable):
        with self._lock:
            self._wildcard_handlers.append(handler)
        if self._connected:
            self.client.subscribe("#")
            logger.info("MQTT subscribed to all topics (#)")

    def publish(self, topic: str, payload: dict, qos: int = 0):
        try:
            self.client.publish(topic, json.dumps(payload), qos=qos)
            logger.debug(f"MQTT → {topic}: {payload}")
        except Exception as e:
            logger.error(f"MQTT publish error on {topic}: {e}")


mqtt_client = MQTTClient()
