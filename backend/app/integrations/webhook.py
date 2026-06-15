import logging
import httpx
import asyncio
from typing import Dict, Any, List
from datetime import datetime, timezone

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class WebhookEngine:
    """
    Enterprise Webhook Engine for EdgeBrain.
    Provides async HTTP forwarding of alerts, ML decisions, and system logs to external sinks.
    """
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.endpoints = getattr(settings, 'WEBHOOK_ENDPOINTS', [])
        
    async def dispatch(self, payload: Dict[str, Any], topic: str = "alert"):
        """Dispatches payload to all registered webhook endpoints."""
        if not self.endpoints:
            return
            
        enriched_payload = {
            "topic": topic,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
            "system": "EdgeBrain Core"
        }
        
        tasks = []
        for url in self.endpoints:
            tasks.append(self._send_single(url, enriched_payload))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for url, res in zip(self.endpoints, results):
            if isinstance(res, Exception):
                logger.error(f"Webhook failed to deliver to {url}: {res}")
            else:
                logger.debug(f"Webhook delivered to {url} [Status: {res}]")
                
    async def _send_single(self, url: str, payload: dict) -> int:
        response = await self.client.post(url, json=payload)
        response.raise_for_status()
        return response.status_code
        
    async def close(self):
        await self.client.aclose()


webhook_engine = WebhookEngine()
