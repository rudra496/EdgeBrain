/*
 * EdgeBrain ESP32 Firmware
 * Reads temperature (DHT11) and motion (PIR) sensors, publishes via MQTT.
 *
 * Hardware:
 *   - DHT11 on GPIO 4 (data pin)
 *   - PIR sensor on GPIO 5 (digital input)
 *   - LED on GPIO 2 (built-in)
 *
 * Configure WiFi and MQTT settings in config.h or below.
 */

#include <WiFi.h>
#include <PubSubClient.h>

// ─── Configuration ─────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

const char* MQTT_HOST     = "192.168.1.100";  // Your EdgeBrain server IP
const int   MQTT_PORT     = 1883;
const char* MQTT_CLIENT_ID = "esp32-edge-01";

const char* DEVICE_ID     = "esp32-edge-01";

// ─── Pins ─────────────────────────────────────────────
#define DHT_PIN   4   // DHT11 data pin
#define PIR_PIN   5   // PIR sensor pin
#define LED_PIN   2   // Built-in LED

// ─── Globals ──────────────────────────────────────────
WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastTempRead = 0;
unsigned long lastMotionCheck = 0;
const long TEMP_INTERVAL = 5000;    // Read temp every 5s
const long MOTION_INTERVAL = 500;   // Check motion every 500ms

bool lastMotionState = LOW;

// ─── WiFi Setup ───────────────────────────────────────
void setupWiFi() {
    Serial.println("[WiFi] Connecting...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.print("[WiFi] Connected! IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println();
        Serial.println("[WiFi] FAILED to connect!");
    }
}

// ─── MQTT Callback ────────────────────────────────────
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    String message = "";
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }

    Serial.print("[MQTT] Command on ");
    Serial.print(topic);
    Serial.print(": ");
    Serial.println(message);

    // Parse simple commands: {"command":"activate","params":{"actuator":"led"}}
    if (message.indexOf("\"led\"") != -1) {
        if (message.indexOf("\"activate\"") != -1) {
            digitalWrite(LED_PIN, HIGH);
            Serial.println("[ACTUATOR] LED ON");
        } else if (message.indexOf("\"deactivate\"") != -1) {
            digitalWrite(LED_PIN, LOW);
            Serial.println("[ACTUATOR] LED OFF");
        }
    }
}

// ─── MQTT Connect ─────────────────────────────────────
void connectMQTT() {
    while (!mqtt.connected()) {
        Serial.print("[MQTT] Connecting...");
        if (mqtt.connect(MQTT_CLIENT_ID)) {
            Serial.println(" connected!");
            // Subscribe to commands for this device
            String cmdTopic = String("device/") + DEVICE_ID + "/command";
            mqtt.subscribe(cmdTopic.c_str());
            Serial.print("[MQTT] Subscribed to: ");
            Serial.println(cmdTopic);
        } else {
            Serial.print(" failed, rc=");
            Serial.println(mqtt.state());
            delay(5000);
        }
    }
}

// ─── Simulated Temperature ────────────────────────────
// Note: Replace with actual DHT11 library if available.
// This uses a simple approximation for demonstration.
float readTemperature() {
    // In production, use DHT library:
    // DHT dht(DHT_PIN, DHT11);
    // return dht.readTemperature();

    // Simulated: base 25°C + noise
    return 25.0 + (random(0, 100) - 50) * 0.1;
}

// ─── Read Motion ──────────────────────────────────────
bool readMotion() {
    return digitalRead(PIR_PIN) == HIGH;
}

// ─── Publish Sensor Data ──────────────────────────────
void publishSensor(const char* deviceType, const char* unit, float value) {
    String topic = String("device/") + DEVICE_ID + "-sensor-" + deviceType + "/data";

    String payload = "{\"device_id\":\"" + String(DEVICE_ID) + "-sensor-" + deviceType
                   + "\",\"device_type\":\"" + String(deviceType)
                   + "\",\"value\":" + String(value, 1)
                   + ",\"unit\":\"" + String(unit) + "\"}";

    mqtt.publish(topic.c_str(), payload.c_str());
    Serial.print("[PUBLISH] ");
    Serial.print(topic);
    Serial.print(" -> ");
    Serial.println(payload);
}

// ─── Setup ────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(1000);
    Serial.println();
    Serial.println("=== EdgeBrain ESP32 ===");

    pinMode(PIR_PIN, INPUT);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    setupWiFi();
    mqtt.setServer(MQTT_HOST, MQTT_PORT);
    mqtt.setCallback(mqttCallback);

    Serial.println("[READY] Starting sensor loop...");
}

// ─── Main Loop ────────────────────────────────────────
void loop() {
    if (!mqtt.connected()) {
        connectMQTT();
    }
    mqtt.loop();

    unsigned long now = millis();

    // Temperature reading every 5s
    if (now - lastTempRead >= TEMP_INTERVAL) {
        lastTempRead = now;
        float temp = readTemperature();
        publishSensor("temp", "C", temp);
    }

    // Motion check every 500ms
    if (now - lastMotionCheck >= MOTION_INTERVAL) {
        lastMotionCheck = now;
        bool motion = readMotion();
        if (motion != lastMotionState) {
            lastMotionState = motion;
            publishSensor("motion", "binary", motion ? 1.0 : 0.0);
        }
    }
}
