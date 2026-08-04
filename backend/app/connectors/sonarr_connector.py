"""Sonarr-Connector (Serien): anstehende Folgen, Download-Queue, hinzufügen.

Sonarr nutzt dieselbe ``X-Api-Key``-Auth wie Overseerr. Graceful Degradation:
ohne Konfiguration liefern alle Methoden leere Ergebnisse statt Fehler.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


def _progress(record: Dict[str, Any]) -> int:
    size = record.get("size") or 0
    left = record.get("sizeleft")
    if not size or left is None:
        return 0
    try:
        return max(0, min(100, round((1 - left / size) * 100)))
    except ZeroDivisionError:
        return 0


class SonarrConnector(BaseConnector):
    name = "sonarr"
    display_name = "Serien (Sonarr)"
    category = "media"
    icon = "📺"

    @property
    def is_configured(self) -> bool:
        return bool(settings.sonarr_url and settings.sonarr_api_key)

    @property
    def base_url(self) -> Optional[str]:
        return settings.sonarr_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"X-Api-Key": settings.sonarr_api_key or "", "Accept": "application/json"}

    async def _probe(self) -> bool:
        await self._get_json("/api/v3/system/status")
        return True

    async def _first(self, path: str, field: str) -> Optional[Any]:
        data = await self._get_json(path)
        return data[0].get(field) if data else None

    async def get_upcoming(self, days: int = 14) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            start = date.today().isoformat()
            end = (date.today() + timedelta(days=days)).isoformat()
            data = await self._get_json(
                "/api/v3/calendar",
                params={"start": start, "end": end, "includeSeries": "true"},
            )
            out: List[Dict[str, Any]] = []
            for ep in data or []:
                series = ep.get("series", {}) or {}
                out.append(
                    {
                        "source": "sonarr", "type": "tv", "icon": self.icon,
                        "title": series.get("title") or ep.get("title", "Serie"),
                        "subtitle": f"S{ep.get('seasonNumber', 0):02d}E{ep.get('episodeNumber', 0):02d} · {ep.get('title', '')}",
                        "date": ep.get("airDateUtc") or ep.get("airDate"),
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("sonarr calendar failed: %s", exc)
            return []

    async def get_queue(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/v3/queue", params={"pageSize": 50})
            records = data.get("records", []) if isinstance(data, dict) else (data or [])
            return [
                {"source": "sonarr", "icon": self.icon, "title": r.get("title", "?"),
                 "status": r.get("status"), "progress": _progress(r)}
                for r in records
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("sonarr queue failed: %s", exc)
            return []

    async def add(self, term: str) -> Optional[str]:
        """Sucht eine Serie und legt sie zum Download an. Gibt den Titel zurück."""
        if not self.is_configured:
            return None
        try:
            results = await self._get_json("/api/v3/series/lookup", params={"term": term})
            if not results:
                return None
            series = results[0]
            qp = settings.sonarr_quality_profile_id or await self._first("/api/v3/qualityprofile", "id")
            root = settings.sonarr_root_folder or await self._first("/api/v3/rootfolder", "path")
            if not qp or not root:
                self.logger.warning("sonarr add: kein qualityProfile/rootFolder verfügbar")
                return None
            payload = {
                **series,
                "qualityProfileId": qp,
                "rootFolderPath": root,
                "monitored": True,
                "addOptions": {"searchForMissingEpisodes": True},
            }
            await self._post_json("/api/v3/series", payload)
            return series.get("title")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("sonarr add failed: %s", exc)
            return None
