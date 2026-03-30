FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir paho-mqtt==2.0.0

COPY device-simulator/simulator.py .

CMD ["python", "simulator.py"]
