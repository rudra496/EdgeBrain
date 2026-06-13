"""API Key authentication for EdgeBrain.

Supports multiple API keys with different scopes (read, write, admin).
Keys are configured via environment variables.
"""
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class APIKeyAuth:
    """Validates API keys and tracks usage."""

    def __init__(self):
        self._usage_stats: dict[str, dict] = {}

    def validate_key(self, key: Optional[str]) -> dict:
        """Validate API key and return key info."""
        if not settings.API_ENABLED:
            # Auth disabled, allow all
            return {"key": "disabled", "scopes": ["admin"]}

        if not key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing API key",
                headers={"WWW-Authenticate": "ApiKey"},
            )

        # Check against configured keys
        if settings.API_KEY and secrets.compare_digest(key, settings.API_KEY):
            self._track_usage("primary")
            return {"key": "primary", "scopes": ["admin"]}

        if settings.API_KEY_READ and secrets.compare_digest(key, settings.API_KEY_READ):
            self._track_usage("read")
            return {"key": "read", "scopes": ["read"]}

        if settings.API_KEY_WRITE and secrets.compare_digest(key, settings.API_KEY_WRITE):
            self._track_usage("write")
            return {"key": "write", "scopes": ["read", "write"]}

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    def _track_usage(self, key_name: str):
        """Track API key usage statistics."""
        if key_name not in self._usage_stats:
            self._usage_stats[key_name] = {"count": 0, "last_used": None}
        self._usage_stats[key_name]["count"] += 1
        self._usage_stats[key_name]["last_used"] = datetime.now(timezone.utc).isoformat()

    def get_stats(self) -> dict:
        """Get API key usage statistics."""
        return {
            "enabled": settings.API_ENABLED,
            "keys": self._usage_stats,
        }


auth_service = APIKeyAuth()


async def verify_api_key(api_key: Optional[str] = Security(api_key_header)) -> dict:
    """FastAPI dependency for API key verification."""
    return auth_service.validate_key(api_key)


async def verify_write_access(key_info: dict = Security(verify_api_key)) -> dict:
    """FastAPI dependency requiring write access."""
    if "admin" not in key_info["scopes"] and "write" not in key_info["scopes"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required",
        )
    return key_info


async def verify_admin_access(key_info: dict = Security(verify_api_key)) -> dict:
    """FastAPI dependency requiring admin access."""
    if "admin" not in key_info["scopes"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return key_info
