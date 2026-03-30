import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.mqtt_client import mqtt_client
from app.core.events import event_queue
from app.api.routes import router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup and shutdown."""
    # ─── Startup ──────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("=" * 60)
    logger.info("  🧠 EdgeBrain v%s — Starting up...", settings.APP_VERSION)
    logger.info("=" * 60)

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("  ✓ Database tables created")

    # Connect MQTT
    mqtt_client.connect()
    logger.info("  ✓ MQTT client initialized")

    # Initialize Redis event queues
    try:
        event_queue.reset()
        logger.info("  ✓ Event queues initialized")
    except Exception as e:
        logger.warning(f"  ⚠ Redis not ready yet: {e}")

    logger.info("=" * 60)
    logger.info("  🚀 EdgeBrain is running!")
    logger.info("  📡 API:    http://localhost:%d/docs", settings.API_PORT)
    logger.info("  🖥️  UI:     http://localhost:3000")
    logger.info("=" * 60)

    yield

    # ─── Shutdown ─────────────────────────────────────────
    logger.info("Shutting down EdgeBrain...")
    mqtt_client.disconnect()
    logger.info("Goodbye!")


app = FastAPI(
    title="EdgeBrain API",
    description="""
    ## 🧠 EdgeBrain — AI-Powered Edge Intelligence Platform

    ### Features
    - **Real-time sensor data** ingestion and processing
    - **Multi-agent AI system** (Data → Decision → Action)
    - **Rule-based** and **statistical anomaly detection**
    - **Actuator control** via MQTT commands
    - **WebSocket** for live dashboard updates
    - **REST API** for programmatic access

    ### Authentication
    No authentication required (local development mode).
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "AI-Powered Edge Intelligence Platform",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/api/v1/health",
        "ws": "/api/v1/ws",
    }


@app.get("/api/v1/info")
def system_info():
    """Detailed system information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "components": {
            "backend": "FastAPI + SQLAlchemy",
            "database": "PostgreSQL",
            "cache": "Redis",
            "messaging": "MQTT (Mosquitto)",
            "ai_engine": "Rule-based + Statistical Anomaly Detection",
            "agents": ["Data Agent", "Decision Agent", "Action Agent"],
        },
        "mqtt_status": "connected" if mqtt_client.is_connected else "disconnected",
    }
