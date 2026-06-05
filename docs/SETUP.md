# Setup Guide

This guide helps you run **EdgeBrain** locally (recommended) using Docker Compose, or natively without Docker.

## Prerequisites

- **Docker** v20.10+ — https://docs.docker.com/get-docker/
- **Docker Compose** v2+ — https://docs.docker.com/compose/install/
- **Git** — https://git-scm.com/
- 4GB RAM minimum (8GB recommended)

> Tip: If you are on Windows, use **PowerShell** or **Git Bash**.

---

## Quick Start (Docker Compose)

```bash
# 1) Clone
git clone https://github.com/rudra496/EdgeBrain.git
cd EdgeBrain

# 2) Start everything
docker compose up --build -d

# 3) Check status
docker compose ps
```

### Open the app

- Dashboard: http://localhost:3000
- API docs (Swagger): http://localhost:8000/docs

---

## Verify Everything Works

```bash
# Health check
curl -s http://localhost:8000/api/v1/health

# Confirm simulated devices are flowing
curl -s http://localhost:8000/api/v1/devices
```

If you see JSON responses, the platform is running correctly.

---

## Accessing Services

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | http://localhost:3000 | React web UI |
| API Docs | http://localhost:8000/docs | Swagger/OpenAPI |
| API Base | http://localhost:8000/api/v1 | REST + WebSocket |
| MQTT | localhost:1883 | Mosquitto broker |
| MQTT (WebSocket) | localhost:9001 | MQTT over WebSocket |

---

## Common Commands

```bash
# View logs
docker compose logs -f

# Stop
docker compose down

# Stop and delete volumes (clears DB/Redis data)
docker compose down -v
```

---

## Running Without Docker (Advanced)

### 1) Start Infrastructure

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

### 2) Initialize Database

```bash
psql postgresql://edgebrain:edgebrain@localhost:5432/edgebrain -f docker/init.sql
```

### 3) Start Backend

```bash
cd backend
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows PowerShell
# .venv\Scripts\Activate.ps1

pip install -r requirements.txt

export DATABASE_URL=postgresql://edgebrain:edgebrain@localhost:5432/edgebrain
export REDIS_URL=redis://localhost:6379/0
export MQTT_HOST=localhost
export MQTT_PORT=1883

uvicorn app.main:app --reload --port 8000
```

### 4) Start Simulator

```bash
cd device-simulator
pip install paho-mqtt==2.0.0
python simulator.py
```

### 5) Start Frontend

```bash
cd frontend
npm install
npm start
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://edgebrain:edgebrain@postgres:5432/edgebrain` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection |
| `MQTT_HOST` | `mosquitto` | MQTT broker host |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `DEBUG` | `true` | Debug mode |

---

## Troubleshooting

### Backend won't start
```bash
docker compose logs backend
```

### No data appearing
```bash
docker compose logs simulator
```

### Frontend can't connect to API
```bash
curl http://localhost:8000/api/v1/health
```
