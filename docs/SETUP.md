# Setup Guide

## Prerequisites

- **Docker** v20.10+ — [Install Guide](https://docs.docker.com/get-docker/)
- **Docker Compose** v2+ — [Install Guide](https://docs.docker.com/compose/install/)
- **Git** — [Install Guide](https://git-scm.com/)
- 4GB RAM minimum, 8GB recommended

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/rudra496/EdgeBrain.git
cd EdgeBrain

# 2. Start everything
docker compose up --build -d

# 3. Wait for services to initialize (~30 seconds)
# 4. Open the dashboard
open http://localhost:3000
```

That's it! The system will:
- Start PostgreSQL with initialized tables
- Start Redis for event queuing
- Start Mosquitto MQTT broker
- Start the FastAPI backend
- Start the device simulator (generates sensor data)
- Start the React dashboard

## Verify Everything Works

```bash
# Check all containers are running
docker compose ps

# Expected: 6 services (postgres, redis, mosquitto, backend, simulator, frontend)

# Check API health
curl http://localhost:8000/api/v1/health

# Check sensor data is flowing
curl http://localhost:8000/api/v1/devices

# View API documentation
open http://localhost:8000/docs
```

## Accessing Services

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | React web UI |
| API Docs | http://localhost:8000/docs | Swagger/OpenAPI |
| API | http://localhost:8000 | REST + WebSocket |
| MQTT | localhost:1883 | Mosquitto broker |
| WebSocket MQTT | localhost:9001 | MQTT over WS |

## Running Without Docker

If you prefer running services natively:

### 1. Start Infrastructure

```bash
# PostgreSQL
docker run -d --name edgebrain-pg \
  -e POSTGRES_USER=edgebrain -e POSTGRES_PASSWORD=edgebrain -e POSTGRES_DB=edgebrain \
  -p 5432:5432 postgres:16-alpine

# Redis
docker run -d --name edgebrain-redis -p 6379:6379 redis:7-alpine

# Mosquitto
docker run -d --name edgebrain-mqtt -p 1883:1883 -p 9001:9001 \
  -v $(pwd)/docker/mosquitto.conf:/mosquitto/config/mosquitto.conf \
  eclipse-mosquitto:2
```

### 2. Initialize Database

```bash
psql postgresql://edgebrain:edgebrain@localhost:5432/edgebrain -f docker/init.sql
```

### 3. Start Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set environment
export DATABASE_URL=postgresql://edgebrain:edgebrain@localhost:5432/edgebrain
export REDIS_URL=redis://localhost:6379/0
export MQTT_HOST=localhost
export MQTT_PORT=1883

uvicorn app.main:app --reload --port 8000
```

### 4. Start Simulator

```bash
cd device-simulator
pip install paho-mqtt==2.0.0
python simulator.py
```

### 5. Start Frontend

```bash
cd frontend
npm install
npm start
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://edgebrain:edgebrain@postgres:5432/edgebrain` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `MQTT_HOST` | `mosquitto` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DEBUG` | `true` | Debug mode |

### Custom Decision Rules

Edit `backend/app/ai/rules.py` to add custom thresholds or create a new strategy class.

### Adding New Devices

Add a new `SimulatedDevice` in `device-simulator/simulator.py`:

```python
SimulatedDevice("room-3-sensor-humidity", "humidity"),
```

## Troubleshooting

### Backend won't start
```bash
docker compose logs backend
# Common: PostgreSQL not ready yet. Docker Compose handles this with healthcheck.
```

### No data appearing
```bash
# Check simulator is running
docker compose logs simulator

# Check MQTT connection
docker compose logs backend | grep MQTT
```

### Frontend can't connect to API
```bash
# Ensure backend is running
curl http://localhost:8000/api/v1/health
# Check CORS — default allows all origins in dev mode
```

### Reset everything
```bash
docker compose down -v  # Removes volumes too
docker compose up --build -d
```
