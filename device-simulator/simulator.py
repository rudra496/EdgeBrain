"""
EdgeBrain Device Simulator
Generates realistic sensor data and publishes via MQTT.
"""
import json
import time
import random
import math
import paho.mqtt.client as mqtt
from datetime import datetime

MQTT_HOST = "localhost"
MQTT_PORT = 1883
INTERVAL_SEC = 2


class SimulatedDevice:
    def __init__(self, device_id: str, device_type: str):
        self.device_id = device_id
        self.device_type = device_type
        self.value = self._init_value()

    def _init_value(self) -> float:
        if self.device_type == "temperature":
            return 25.0
        elif self.device_type == "motion":
            return 0.0
        elif self.device_type == "energy":
            return 120.0
        return 0.0

    def generate(self) -> dict:
        if self.device_type == "temperature":
            # Slow drift with noise + occasional spike
            self.value += random.gauss(0, 0.3)
            self.value += 0.01 * (25 - self.value)  # mean-revert to 25
            if random.random() < 0.01:  # 1% chance of spike
                self.value += random.uniform(5, 15)
            self.value = max(10, min(60, self.value))
            return {"device_id": self.device_id, "device_type": "temperature",
                    "value": round(self.value, 1), "unit": "°C"}

        elif self.device_type == "motion":
            # Random motion bursts
            if random.random() < 0.3:
                self.value = random.uniform(0.5, 1.0)
            else:
                self.value *= 0.7  # decay
            return {"device_id": self.device_id, "device_type": "motion",
                    "value": round(self.value, 2), "unit": "binary"}

        elif self.device_type == "energy":
            # Base load + time-of-day pattern + noise
            hour = datetime.now().hour
            base = 120 + 80 * math.sin((hour - 6) * math.pi / 12)
            self.value = base + random.gauss(0, 20)
            if random.random() < 0.005:  # rare spike
                self.value += random.uniform(200, 400)
            self.value = max(0, self.value)
            return {"device_id": self.device_id, "device_type": "energy",
                    "value": round(self.value, 1), "unit": "W"}

        return {"device_id": self.device_id, "device_type": self.device_type,
                "value": 0, "unit": ""}


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="device-simulator",
    )

    print(f"🔌 Connecting to MQTT at {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    print("✅ Connected!")

    devices = [
        SimulatedDevice("room-1-sensor-temp", "temperature"),
        SimulatedDevice("room-1-sensor-motion", "motion"),
        SimulatedDevice("room-1-meter-energy", "energy"),
        SimulatedDevice("room-2-sensor-temp", "temperature"),
        SimulatedDevice("room-2-sensor-motion", "motion"),
    ]

    def on_command(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"📥 Command received on {msg.topic}: {payload}")
        except Exception as e:
            print(f"Command parse error: {e}")

    # Subscribe to command topics for actuators
    client.subscribe("device/+/command")
    client.on_message = on_command

    print(f"🚀 Simulating {len(devices)} devices (interval: {INTERVAL_SEC}s)")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            for device in devices:
                data = device.generate()
                topic = f"device/{device.device_id}/data"
                client.publish(topic, json.dumps(data))
                print(f"📤 {topic}: {data['value']}{data['unit']}")
            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n🛑 Stopping simulator...")
        client.disconnect()


if __name__ == "__main__":
    main()
