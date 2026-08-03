"""Einkaufslisten-Connector für KitchenOwl (https://kitchenowl.org).

Hermes ergänzt Produkte automatisch (z.B. via Sprache/KI: "Milch ist leer").
Die Endpunkte variieren je KitchenOwl-Version; alle Aufrufe sind defensiv.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class KitchenOwlConnector(BaseConnector):
    name = "kitchenowl"
    display_name = "Einkauf (KitchenOwl)"
    category = "shopping"
    icon = "🛒"

    @property
    def is_configured(self) -> bool:
        return bool(settings.kitchenowl_url and settings.kitchenowl_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.kitchenowl_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.kitchenowl_token}"}

    async def _probe(self) -> bool:
        # /api/health ist in vielen KitchenOwl-Versionen ohne Auth erreichbar.
        async with self._client() as client:
            resp = await client.get("/api/health")
            return resp.status_code < 500

    async def _first_list_id(self) -> Optional[int]:
        try:
            lists = await self._get_json("/api/shoppinglist")
            if isinstance(lists, list) and lists:
                return lists[0].get("id")
        except Exception as exc:  # noqa: BLE001
            self.logger.debug("kitchenowl list lookup failed: %s", exc)
        return None

    async def get_items(self, list_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Aktuelle Einträge der Einkaufsliste."""
        if not self.is_configured:
            return []
        try:
            list_id = list_id or await self._first_list_id()
            if list_id is None:
                return []
            raw = await self._get_json(f"/api/shoppinglist/{list_id}/items")
            items = raw if isinstance(raw, list) else raw.get("items", [])
            return [
                {
                    "id": it.get("id"),
                    "name": it.get("name") or (it.get("item") or {}).get("name", "Artikel"),
                    "description": it.get("description", ""),
                    "category": (it.get("category") or {}).get("name") if isinstance(it.get("category"), dict) else it.get("category"),
                }
                for it in items
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("kitchenowl get_items failed: %s", exc)
            return []

    async def add_item(self, name: str, list_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Fügt einen Artikel per Name hinzu."""
        if not self.is_configured:
            return None
        try:
            list_id = list_id or await self._first_list_id()
            if list_id is None:
                return None
            async with self._client() as client:
                resp = await client.post(
                    f"/api/shoppinglist/{list_id}/add-item-by-name",
                    json={"name": name},
                )
                resp.raise_for_status()
                return {"name": name, "added": True}
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("kitchenowl add_item failed: %s", exc)
            return None
