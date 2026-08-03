"""Medien-Connector für Plex (aus dem Legacy Family Hub übernommen).

Optionales Modul: zeigt aktive Streams und neu hinzugefügte Inhalte.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class PlexConnector(BaseConnector):
    name = "plex"
    display_name = "Medien (Plex)"
    category = "media"
    icon = "🎬"

    @property
    def is_configured(self) -> bool:
        return bool(settings.plex_url and settings.plex_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.plex_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Accept": "application/json", "X-Plex-Token": settings.plex_token or ""}

    async def _probe(self) -> bool:
        data = await self._get_json("/status/sessions")
        return isinstance(data, dict)

    async def get_active_streams(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/status/sessions")
            sessions = data.get("MediaContainer", {}).get("Metadata", [])
            streams = []
            for s in sessions:
                title = s.get("title", "Unbekannt")
                if s.get("type") == "episode":
                    title = f"{s.get('grandparentTitle', '')} – {title}"
                streams.append(
                    {
                        "title": title,
                        "type": s.get("type"),
                        "user": s.get("User", {}).get("title", "Unbekannt"),
                        "progress": s.get("viewOffset", 0),
                        "duration": s.get("duration", 0),
                    }
                )
            return streams
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("plex get_active_streams failed: %s", exc)
            return []

    async def get_recent(self, limit: int = 5) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/library/recentlyAdded")
            items = data.get("MediaContainer", {}).get("Metadata", [])[:limit]
            return [
                {"title": i.get("title", "Unbekannt"), "type": i.get("type"), "year": i.get("year")}
                for i in items
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("plex get_recent failed: %s", exc)
            return []
