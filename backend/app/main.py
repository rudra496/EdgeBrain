import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.database import engine, Base
from app.core.mqtt_client import mqtt_client
from app.api.routes import router, ws_manager

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("🧠 EdgeBrain starting up...")

    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Connect MQTT
    mqtt_client.connect()
    logger.info("MQTT connected")

    # Start event processor
    from app.core.events import event_queue
    event_queue.redis.delete("edgebrain:events")
    event_queue.redis.delete("edgebrain:alerts")
    logger.info("Event queues initialized")

    yield

    # Shutdown
    mqtt_client.disconnect()
    logger.info("🧠 EdgeBrain shut down")


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Edge Intelligence Platform",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "EdgeBrain",
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
