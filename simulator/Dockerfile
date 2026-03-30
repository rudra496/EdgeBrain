FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir paho-mqtt==2.0.0

COPY device-simulator/simulator.py .

ENV MQTT_HOST=mosquitto
ENV MQTT_PORT=1883

CMD ["python", "simulator.py"]
