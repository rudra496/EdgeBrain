# EdgeBrain Examples

This directory contains example scripts demonstrating how to integrate various Edge AI and machine learning tasks with the EdgeBrain platform. 

The examples simulate edge devices processing data (like images, webcam feeds, or text) and securely transmitting the extracted insights (inferences) to the EdgeBrain backend via MQTT.

## Available Examples

1. **`image_classification.py`**  
   Simulates a Raspberry Pi capturing an image, running a lightweight classification model, and publishing the inferred class and confidence score to EdgeBrain.

2. **`object_detection.py`**  
   Simulates processing a live webcam feed using an object detection model (e.g., YOLO) to count the number of detected persons in a room, sending the count to EdgeBrain.

3. **`sentiment_analysis.py`**  
   Demonstrates how non-hardware AI tasks can be integrated. It performs sentiment analysis on a text stream and sends a sentiment score (-1.0 to 1.0) to EdgeBrain.

## Prerequisites

To run these examples, ensure you have the required dependencies installed. You can install the MQTT client library using pip:

```bash
pip install paho-mqtt
```

*Note: In a real-world scenario, you would also need the respective ML libraries (e.g., `opencv-python`, `tensorflow`, `torch`, `transformers`) depending on the actual models you choose to deploy.*

## Usage

1. Ensure the EdgeBrain platform (including the MQTT broker) is running. By default, the scripts attempt to connect to `localhost:1883`.
2. Run any of the example scripts:

```bash
python image_classification.py
```

3. Open the EdgeBrain dashboard or query the REST API to see the live data flowing from the simulated edge devices!
