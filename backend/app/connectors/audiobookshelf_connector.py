"""Hörbuch-Connector für Audiobookshelf (https://www.audiobookshelf.org).

Zeigt aktuell laufende Hörbücher/Podcasts – wichtig für den Familien-Medienstatus.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class AudiobookshelfConnector(BaseConnector):
    name = "audiobookshelf"
    display_name = "Hörbücher (Audiobookshelf)"
    category = "media"
    icon = "📚"

    @property
    def is_configured(self) -> bool:
        return bool(settings.audiobookshelf_url and settings.audiobookshelf_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.audiobookshelf_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.audiobookshelf_token}"}

    async def _probe(self) -> bool:
        data = await self._get_json("/api/me/listening-sessions")
        return data is not None

    async def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Aktuell laufende Wiedergaben (in den letzten 5 Minuten aktualisiert)."""
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/me/listening-sessions")
            sessions = data if isinstance(data, list) else []
            if not sessions:
                data = await self._get_json("/api/sessions")
                all_sessions = data.get("sessions", []) if isinstance(data, dict) else (data or [])
                now = time.time()
                sessions = [s for s in all_sessions if now - (s.get("updatedAt", 0) / 1000) < 300]

            out: List[Dict[str, Any]] = []
            for s in sessions[:5]:
                meta = s.get("mediaMetadata", {}) or {}
                out.append(
                    {
                        "source": "audiobookshelf",
                        "title": s.get("displayTitle", meta.get("title", "Hörbuch")),
                        "subtitle": s.get("displayAuthor", meta.get("author", "")),
                        "type": s.get("mediaType", "audiobook"),
                        "user": (s.get("user", {}) or {}).get("username", "Unbekannt"),
                        "icon": "📚",
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("audiobookshelf sessions failed: %s", exc)
            return []

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/libraries")
            libs = data.get("libraries", []) if isinstance(data, dict) else []
            results: List[Dict[str, Any]] = []
            for lib in libs[:3]:
                lib_id = lib.get("id")
                if not lib_id:
                    continue
                found = await self._get_json(f"/api/libraries/{lib_id}/search", params={"q": query, "limit": limit})
                for book in (found.get("book", []) if isinstance(found, dict) else [])[:limit]:
                    li = book.get("libraryItem", {}) if isinstance(book, dict) else {}
                    meta = (li.get("media", {}) or {}).get("metadata", {}) or {}
                    results.append(
                        {
                            "title": meta.get("title", "Hörbuch"),
                            "subtitle": meta.get("authorName", ""),
                            "url": f"{(settings.audiobookshelf_url or '').rstrip('/')}/item/{li.get('id')}",
                            "source": self.display_name,
                            "category": self.category,
                            "icon": self.icon,
                        }
                    )
            return results[:limit]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("audiobookshelf search failed: %s", exc)
            return []
