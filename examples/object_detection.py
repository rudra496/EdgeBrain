"""
Example: Object Detection with Webcam

This script demonstrates how to integrate a webcam object detection model
with EdgeBrain. It captures frames from a camera, runs a simulated object
detection model, and publishes the number of detected persons to the
EdgeBrain system via MQTT.

Requirements:
- paho-mqtt
- opencv-python (for actual camera usage)

Usage:
    python object_detection.py
"""

import time
import json
import random
import paho.mqtt.client as mqtt

# Configuration for EdgeBrain MQTT Broker
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "edgebrain/devices/webcam_01/data"

def simulate_object_detection():
    """
    Simulates object detection (e.g., YOLO, MobileNet) returning the count
    of people detected in the camera frame.
    In a real scenario, you would use cv2.VideoCapture() and a model here.
    """
    return random.randint(0, 5)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Connected to EdgeBrain MQTT Broker!")
    else:
        print(f"Failed to connect, return code {rc}")

def main():
    client = mqtt.Client(client_id="webcam_detector_01")
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except ConnectionRefusedError:
        print(f"Error: Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        print("Make sure the EdgeBrain infrastructure is running.")
        return

    client.loop_start()
    
    print("Starting webcam object detection stream...")
    try:
        while True:
            # Run detection (simulated)
            person_count = simulate_object_detection()
            
            # Prepare payload for EdgeBrain
            payload = {
                "device_id": "webcam_01",
                "device_type": "camera",
                "value": person_count,
                "unit": "persons",
                "room": "living_room",
                "extra": {
                    "model": "yolov8n",
                    "confidence": round(random.uniform(0.7, 0.99), 2)
                }
            }
            
            # Publish to EdgeBrain
            client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"Published detection: {person_count} persons detected")
            
            time.sleep(2) # Process a frame every 2 seconds
            
    except KeyboardInterrupt:
        print("Stopping object detection.")
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
