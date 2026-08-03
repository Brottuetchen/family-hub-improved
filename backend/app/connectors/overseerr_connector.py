"""Media-Request-Connector für Overseerr (https://overseerr.dev).

Zeigt offene Film-/Serien-Anfragen der Familie (Wunschliste fürs Media-System).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class OverseerrConnector(BaseConnector):
    name = "overseerr"
    display_name = "Media-Requests (Overseerr)"
    category = "media"
    icon = "🎞️"

    @property
    def is_configured(self) -> bool:
        return bool(settings.overseerr_url and settings.overseerr_api_key)

    @property
    def base_url(self) -> Optional[str]:
        return settings.overseerr_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"X-Api-Key": settings.overseerr_api_key or "", "Accept": "application/json"}

    async def _probe(self) -> bool:
        await self._get_json("/api/v1/status")
        return True

    async def get_pending_requests(self, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json(
                "/api/v1/request", params={"take": limit, "skip": 0, "filter": "pending"}
            )
            results = data.get("results", []) if isinstance(data, dict) else []
            out = []
            for req in results[:limit]:
                media = req.get("media", {}) or {}
                out.append(
                    {
                        "id": req.get("id"),
                        "type": media.get("mediaType", "unknown"),
                        "title": media.get("title") or media.get("name", "Anfrage"),
                        "requested_by": (req.get("requestedBy", {}) or {}).get("displayName", "Unbekannt"),
                        "created_at": req.get("createdAt"),
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("overseerr requests failed: %s", exc)
            return []
