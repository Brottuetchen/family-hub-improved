"""Inventar-Connector für Homebox (https://homebox.software).

Alles im Haushalt: Fernseher, Fahrräder, Werkzeuge, Garantien, Seriennummern.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class HomeboxConnector(BaseConnector):
    name = "homebox"
    display_name = "Inventar (Homebox)"
    category = "inventory"
    icon = "📦"

    @property
    def is_configured(self) -> bool:
        return bool(settings.homebox_url and settings.homebox_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.homebox_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.homebox_token}"}

    async def _probe(self) -> bool:
        async with self._client() as client:
            resp = await client.get("/api/v1/status")
            return resp.status_code < 500

    async def get_items(self, limit: int = 50) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/v1/items", params={"pageSize": limit})
            items = data.get("items", []) if isinstance(data, dict) else data
            return [self._normalize(it) for it in (items or [])]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("homebox get_items failed: %s", exc)
            return []

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/v1/items", params={"q": query, "pageSize": limit})
            items = data.get("items", []) if isinstance(data, dict) else data
            out = []
            for it in (items or [])[:limit]:
                out.append(
                    {
                        "title": it.get("name", "Gegenstand"),
                        "subtitle": (it.get("location") or {}).get("name", "") if isinstance(it.get("location"), dict) else "",
                        "url": f"{(settings.homebox_url or '').rstrip('/')}/item/{it.get('id')}",
                        "source": self.display_name,
                        "category": self.category,
                        "icon": self.icon,
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("homebox search failed: %s", exc)
            return []

    def _normalize(self, it: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": it.get("id"),
            "name": it.get("name", "Gegenstand"),
            "description": it.get("description", ""),
            "quantity": it.get("quantity", 1),
            "location": (it.get("location") or {}).get("name") if isinstance(it.get("location"), dict) else None,
        }
