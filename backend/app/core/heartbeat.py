"""Device heartbeat and offline detection.

Tracks device last-seen timestamps and marks devices as offline
when they haven't sent data within the configured timeout.
"""
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class DeviceHeartbeat:
    """Tracks device heartbeats and detects offline devices."""

    def __init__(self):
        self._last_seen: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def update_heartbeat(self, device_id: str):
        """Update last-seen timestamp for a device."""
        with self._lock:
            self._last_seen[device_id] = datetime.now(timezone.utc)

    def get_last_seen(self, device_id: str) -> Optional[datetime]:
        """Get last-seen timestamp for a device."""
        with self._lock:
            return self._last_seen.get(device_id)

    def is_online(self, device_id: str) -> bool:
        """Check if device is online (sent data within timeout)."""
        with self._lock:
            last_seen = self._last_seen.get(device_id)
            if not last_seen:
                return False
            
            timeout = timedelta(seconds=settings.DEVICE_HEARTBEAT_TIMEOUT_S)
            return (datetime.now(timezone.utc) - last_seen) < timeout

    def get_offline_devices(self) -> list[dict]:
        """Get list of devices that are offline."""
        offline = []
        now = datetime.now(timezone.utc)
        timeout = timedelta(seconds=settings.DEVICE_HEARTBEAT_TIMEOUT_S)

        with self._lock:
            for device_id, last_seen in self._last_seen.items():
                if (now - last_seen) >= timeout:
                    offline.append({
                        "device_id": device_id,
                        "last_seen": last_seen.isoformat(),
                        "offline_seconds": (now - last_seen).total_seconds(),
                    })

        return offline

    def get_online_devices(self) -> list[str]:
        """Get list of device IDs that are online."""
        online = []
        now = datetime.now(timezone.utc)
        timeout = timedelta(seconds=settings.DEVICE_HEARTBEAT_TIMEOUT_S)

        with self._lock:
            for device_id, last_seen in self._last_seen.items():
                if (now - last_seen) < timeout:
                    online.append(device_id)

        return online

    def get_stats(self) -> dict:
        """Get heartbeat tracking statistics."""
        with self._lock:
            total = len(self._last_seen)
            online = len(self.get_online_devices())
            offline = total - online

        return {
            "total_devices": total,
            "online": online,
            "offline": offline,
            "heartbeat_timeout_s": settings.DEVICE_HEARTBEAT_TIMEOUT_S,
        }

    def clear(self):
        """Clear all heartbeat data."""
        with self._lock:
            self._last_seen.clear()
            logger.info("Heartbeat data cleared")


device_heartbeat = DeviceHeartbeat()
