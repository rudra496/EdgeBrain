"""
Example: Sentiment Analysis on Text

This script demonstrates integrating a text-based AI task with EdgeBrain.
It performs sentiment analysis on incoming text streams (e.g., social media
mentions or customer feedback) and publishes the sentiment score.

Requirements:
- paho-mqtt

Usage:
    python sentiment_analysis.py
"""

import time
import json
import random
import paho.mqtt.client as mqtt

# Configuration for EdgeBrain MQTT Broker
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "edgebrain/devices/sentiment_analyzer_01/data"

SAMPLE_TEXTS = [
    "The new feature is amazing, I love it!",
    "System is completely broken, please fix immediately.",
    "It's okay, but could be better.",
    "I'm neutral on this change.",
    "Absolutely terrible experience today."
]

def analyze_sentiment(text):
    """
    Simulates a sentiment analysis model (e.g., HuggingFace transformers).
    Returns a sentiment score between -1.0 (negative) and 1.0 (positive).
    """
    if "amazing" in text or "love" in text:
        return 0.9
    elif "broken" in text or "terrible" in text:
        return -0.8
    elif "better" in text:
        return 0.2
    else:
        return 0.0

def main():
    client = mqtt.Client(client_id="sentiment_analyzer_01")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
    except ConnectionRefusedError:
        print(f"Error: Could not connect to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}")
        return

    print("Starting Sentiment Analysis stream...")
    
    try:
        while True:
            text = random.choice(SAMPLE_TEXTS)
            score = analyze_sentiment(text)
            
            # Publish to EdgeBrain
            payload = {
                "device_id": "sentiment_analyzer_01",
                "device_type": "text_analyzer",
                "value": score,
                "unit": "sentiment_score",
                "room": "cloud_service",
                "extra": {
                    "source_text": text
                }
            }
            
            client.publish(MQTT_TOPIC, json.dumps(payload))
            print(f"Analyzed text: '{text}' | Score: {score}")
            
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("Stopping sentiment analysis.")
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
