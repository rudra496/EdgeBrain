"""Rate limiting for EdgeBrain API using slowapi.

Provides per-IP and per-API-key rate limiting with configurable limits.
"""
import logging
from typing import Callable

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _get_rate_limit_key(request: Request) -> str:
    """Get rate limit key from API key header or IP address."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key[:8]}"  # Use first 8 chars to avoid storing full key
    return get_remote_address(request)


# Create limiter instance
limiter = Limiter(
    key_func=_get_rate_limit_key,
    enabled=settings.RATE_LIMIT_ENABLED,
)


def get_rate_limit_middleware():
    """Return configured rate limiting middleware."""
    return SlowAPIMiddleware


def get_limiter() -> Limiter:
    """Get the limiter instance."""
    return limiter
