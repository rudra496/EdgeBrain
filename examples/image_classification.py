"""
Example: Image Classification on Raspberry Pi

This script demonstrates how an edge device like a Raspberry Pi can run
an image classification model and report the results to EdgeBrain.
It classifies an image and sends a confidence score or label to the system.

Requirements:
- paho-mqtt

Usage:
    python image_classification.py
"""

import time
import json
import random
import paho.mqtt.client as mqtt

# Configuration for EdgeBrain MQTT Broker
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "edgebrain/devices/rpi_cam_01/data"

CLASSES = ["cat", "dog", "person", "car", "unknown"]

def classify_image():
    """
    Simulates capturing an image on a Raspberry Pi and running a lightweight
    classification model (e.g., TensorFlow Lite).
    """
    detected_class = random.choice(CLASSES)
    confidence = random.uniform(0.5, 0.99)
    return detected_class, confidence

def main():
    client = mqtt.Client(client_id="rpi_classifier_01")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except ConnectionRefusedError:
        print(f"Error: Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        return

    print("Starting Raspberry Pi Image Classifier...")
    
    try:
        while True:
            label, conf = classify_image()
            
            # EdgeBrain expects a numerical value as the primary metric.
            # We can use confidence as the value, and pass the label in 'extra'.
            payload = {
                "device_id": "rpi_cam_01",
                "device_type": "rpi_camera",
                "value": conf,
                "unit": "confidence",
                "room": "garage",
                "extra": {
                    "detected_class": label
                }
            }
            
            client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"Classified image as '{label}' (conf: {conf:.2f}). Published to EdgeBrain.")
            
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("Shutting down classifier.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
