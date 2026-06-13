import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.events import event_queue
from app.core.mqtt_client import mqtt_client
from app.core.rate_limiter import limiter
from app.core.metrics import MetricsMiddleware

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    Base.metadata.create_all(bind=engine)
    mqtt_client.connect()
    event_queue.connect()
    logger.info("EdgeBrain started successfully")
    yield
    logger.info("Shutting down EdgeBrain...")
    mqtt_client.disconnect()
    event_queue.close()
    logger.info("EdgeBrain shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

if settings.RATE_LIMIT_ENABLED:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"error": "Rate limit exceeded", "detail": str(exc.detail)},
        )

app.add_middleware(MetricsMiddleware)
app.include_router(router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


@app.get(f"{settings.API_V1_PREFIX}/health")
def health():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get(f"{settings.API_V1_PREFIX}/info")
def info():
    cors_origins = settings.CORS_ORIGINS
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "debug": settings.DEBUG,
        "api": {
            "v1_prefix": settings.API_V1_PREFIX,
            "docs": f"{settings.API_V1_PREFIX}/docs",
            "redoc": f"{settings.API_V1_PREFIX}/redoc",
        },
        "auth": {"enabled": settings.API_ENABLED},
        "rate_limiting": {
            "enabled": settings.RATE_LIMIT_ENABLED,
            "per_minute": settings.RATE_LIMIT_PER_MINUTE,
            "per_hour": settings.RATE_LIMIT_PER_HOUR,
        },
        "components": {
            "database": "PostgreSQL",
            "cache": "Redis",
            "messaging": "MQTT (Mosquitto)",
            "ai_engine": "Rule-based + Statistical Anomaly Detection",
            "agents": ["Data Agent", "Decision Agent", "Action Agent"],
        },
        "mqtt_status": "connected" if mqtt_client.is_connected else "disconnected",
        "cors_origins": cors_origins,
    }
