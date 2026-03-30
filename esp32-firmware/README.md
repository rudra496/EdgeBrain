# EdgeBrain ESP32 Firmware

Optional real hardware integration for EdgeBrain.

## Hardware

| Component | Pin | Notes |
|-----------|-----|-------|
| DHT11 | GPIO 4 | Temperature sensor |
| PIR Sensor | GPIO 5 | Motion detector |
| LED | GPIO 2 | Built-in |
| Buzzer | GPIO 13 | Optional alarm |

## Setup

1. Open in [Arduino IDE](https://www.arduino.cc/en/software)
2. Select board: **ESP32 Dev Module**
3. Install libraries: `WiFi`, `PubSubClient`
4. Edit `main.ino` with your WiFi + MQTT broker IP
5. Upload and monitor via Serial (115200 baud)

## Configuration

```cpp
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_HOST     = "192.168.1.100";  // EdgeBrain server
```

## Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `device/esp32-edge-01-sensor-temp/data` | Publish | Temperature readings |
| `device/esp32-edge-01-sensor-motion/data` | Publish | Motion detection |
| `device/esp32-edge-01/command` | Subscribe | Actuator commands |

## Dependencies

- [ESP32 Arduino Core](https://github.com/espressif/arduino-esp32)
- [PubSubClient](https://github.com/knolleary/pubsubclient)
- [DHT sensor library](https://github.com/adafruit/DHT-sensor-library) (for real DHT11)
