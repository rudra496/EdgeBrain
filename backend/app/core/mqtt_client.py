import json
import logging
import paho.mqtt.client as mqtt
from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="edgebrain-backend",
        )
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self._message_handlers = {}
        self._connected = False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info(f"MQTT connected with result code {reason_code}")
        self._connected = True

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            for handler in self._message_handlers.get(topic, []):
                handler(topic, payload)
            for handler in self._message_handlers.get("#", []):
                handler(topic, payload)
        except Exception as e:
            logger.error(f"MQTT message error: {e}")

    def connect(self):
        self.client.connect(settings.MQTT_HOST, settings.MQTT_PORT, settings.MQTT_KEEPALIVE)
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def subscribe(self, topic: str, handler):
        if topic not in self._message_handlers:
            self._message_handlers[topic] = []
            self.client.subscribe(topic)
            logger.info(f"Subscribed to {topic}")
        self._message_handlers[topic].append(handler)

    def subscribe_all(self, handler):
        self._message_handlers.setdefault("#", []).append(handler)

    def publish(self, topic: str, payload: dict):
        self.client.publish(topic, json.dumps(payload))
        logger.debug(f"Published to {topic}: {payload}")


mqtt_client = MQTTClient()
