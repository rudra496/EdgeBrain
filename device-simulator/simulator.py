"""
EdgeBrain Device Simulator
============================
Simulates realistic IoT sensor data and publishes via MQTT.

Devices:
  - Room 1: Temperature, Motion, Energy, Humidity, Light
  - Room 2: Temperature, Motion, Energy
  - Server Room: Temperature, Humidity, Energy

Features:
  - Realistic patterns (time-of-day, noise, drift, spikes)
  - Receives and logs actuator commands
  - Configurable via environment variables
"""
import json
import time
import random
import math
import os
import paho.mqtt.client as mqtt
from datetime import datetime

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
INTERVAL_SEC = float(os.getenv("SIM_INTERVAL", "2"))


class SimulatedDevice:
    """Simulates a single IoT sensor device."""

    VALID_TYPES = {
        "temperature": {"unit": "°C", "base": 24.0, "noise": 0.3, "min": 10, "max": 60},
        "motion": {"unit": "binary", "base": 0.0, "noise": 0.0, "min": 0, "max": 1},
        "energy": {"unit": "W", "base": 120.0, "noise": 20.0, "min": 0, "max": 10000},
        "humidity": {"unit": "%", "base": 50.0, "noise": 1.5, "min": 0, "max": 100},
        "light": {"unit": "lux", "base": 500.0, "noise": 50.0, "min": 0, "max": 100000},
    }

    def __init__(self, device_id: str, device_type: str, room: str = "default",
                 base: float | None = None, noise: float | None = None):
        self.device_id = device_id
        self.device_type = device_type
        self.room = room
        config = self.VALID_TYPES.get(device_type, self.VALID_TYPES["temperature"])
        self.value = base if base is not None else config["base"]
        self.noise_scale = noise if noise is not None else config["noise"]
        self.min_val = config["min"]
        self.max_val = config["max"]
        self.unit = config["unit"]
        self._spike_cooldown = 0

    def generate(self) -> dict:
        now = datetime.now()
        hour = now.hour + now.minute / 60.0

        if self.device_type == "temperature":
            # Day/night cycle: warmer during day
            day_effect = 3.0 * math.sin((hour - 6) * math.pi / 12)
            self.value += random.gauss(0, self.noise_scale)
            self.value += 0.02 * (self.VALID_TYPES["temperature"]["base"] + day_effect - self.value)
            # Rare spike (overheating simulation)
            if self._spike_cooldown <= 0 and random.random() < 0.005:
                self.value += random.uniform(8, 18)
                self._spike_cooldown = 30
            self._spike_cooldown = max(0, self._spike_cooldown - 1)
            self.value = max(self.min_val, min(self.max_val, self.value))

        elif self.device_type == "motion":
            # Random bursts of motion
            if random.random() < 0.3:
                self.value = random.uniform(0.5, 1.0)
            else:
                self.value *= 0.6  # exponential decay
            self.value = max(self.min_val, min(self.max_val, self.value))

        elif self.device_type == "energy":
            # Day/night pattern: higher during work hours
            if 8 <= hour <= 18:
                base = self.VALID_TYPES["energy"]["base"] * 1.5
            elif 22 <= hour or hour <= 5:
                base = self.VALID_TYPES["energy"]["base"] * 0.4
            else:
                base = self.VALID_TYPES["energy"]["base"]
            self.value = base + random.gauss(0, self.noise_scale)
            # Rare spike (equipment turning on)
            if self._spike_cooldown <= 0 and random.random() < 0.005:
                self.value += random.uniform(200, 500)
                self._spike_cooldown = 20
            self._spike_cooldown = max(0, self._spike_cooldown - 1)
            self.value = max(self.min_val, self.value)

        elif self.device_type == "humidity":
            # Slow drift, inversely correlated with temperature
            temp_drift = -0.1 * (self.value - 50.0) * 0.01
            self.value += random.gauss(0, self.noise_scale) + temp_drift
            self.value = max(self.min_val, min(self.max_val, self.value))

        elif self.device_type == "light":
            # Strongly tied to time of day
            if 6 <= hour <= 18:
                base = self.VALID_TYPES["light"]["base"] * (0.5 + 0.5 * math.sin((hour - 6) * math.pi / 12))
            else:
                base = 50.0  # ambient
            self.value = base + random.gauss(0, self.noise_scale)
            self.value = max(self.min_val, self.value)

        payload = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "value": round(self.value, 2),
            "unit": self.unit,
            "room": self.room,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        return payload


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"device-simulator-{random.randint(1000, 9999)}",
    )

    print(f"🔌 Connecting to MQTT at {MQTT_HOST}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        print("✅ Connected to MQTT broker!")
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")
        print("   Make sure Mosquitto is running.")
        return

    devices = [
        # Room 1 — Full sensor suite
        SimulatedDevice("room-1-sensor-temp", "temperature", "room-1"),
        SimulatedDevice("room-1-sensor-motion", "motion", "room-1"),
        SimulatedDevice("room-1-meter-energy", "energy", "room-1"),
        SimulatedDevice("room-1-sensor-humidity", "humidity", "room-1"),
        SimulatedDevice("room-1-sensor-light", "light", "room-1"),

        # Room 2 — Basic sensors
        SimulatedDevice("room-2-sensor-temp", "temperature", "room-2"),
        SimulatedDevice("room-2-sensor-motion", "motion", "room-2"),
        SimulatedDevice("room-2-meter-energy", "energy", "room-2"),

        # Server Room — Temperature & energy monitoring
        SimulatedDevice("server-room-sensor-temp", "temperature", "server-room", base=22.0, noise=0.2),
        SimulatedDevice("server-room-sensor-humidity", "humidity", "server-room", base=40.0, noise=1.0),
        SimulatedDevice("server-room-meter-energy", "energy", "server-room", base=300.0, noise=15.0),
    ]

    def on_command(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            device_id = topic.split("/")[1]
            print(f"  📥 Command → {device_id}: {json.dumps(payload)}")
        except Exception as e:
            print(f"  ⚠ Command parse error: {e}")

    client.subscribe("device/+/command")
    client.on_message = on_command

    print(f"\n🚀 Simulating {len(devices)} devices (interval: {INTERVAL_SEC}s)")
    print("   Rooms: room-1 (5 sensors), room-2 (3 sensors), server-room (3 sensors)")
    print("   Press Ctrl+C to stop\n")

    msg_count = 0
    try:
        while True:
            for device in devices:
                data = device.generate()
                topic = f"device/{device.device_id}/data"
                client.publish(topic, json.dumps(data))
                msg_count += 1

            print(f"  📤 [{msg_count:05d}] {datetime.now().strftime('%H:%M:%S')} — "
                  f"{len(devices)} readings sent", end="\r")
            time.sleep(INTERVAL_SEC)
    except KeyboardInterrupt:
        print(f"\n\n🛑 Stopped after {msg_count} messages")
        client.disconnect()
        print("👋 Goodbye!")


if __name__ == "__main__":
    main()
