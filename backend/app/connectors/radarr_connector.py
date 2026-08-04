"""Radarr-Connector (Filme): anstehende Releases, Download-Queue, hinzufügen.

Radarr nutzt dieselbe ``X-Api-Key``-Auth wie Sonarr/Overseerr. Graceful
Degradation: ohne Konfiguration liefern alle Methoden leere Ergebnisse.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector
from app.connectors.sonarr_connector import _progress


class RadarrConnector(BaseConnector):
    name = "radarr"
    display_name = "Filme (Radarr)"
    category = "media"
    icon = "🎬"

    @property
    def is_configured(self) -> bool:
        return bool(settings.radarr_url and settings.radarr_api_key)

    @property
    def base_url(self) -> Optional[str]:
        return settings.radarr_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"X-Api-Key": settings.radarr_api_key or "", "Accept": "application/json"}

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
            data = await self._get_json("/api/v3/calendar", params={"start": start, "end": end})
            out: List[Dict[str, Any]] = []
            for m in data or []:
                out.append(
                    {
                        "source": "radarr", "type": "movie", "icon": self.icon,
                        "title": m.get("title", "Film"),
                        "subtitle": str(m.get("year") or ""),
                        "date": m.get("digitalRelease") or m.get("physicalRelease") or m.get("inCinemas"),
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("radarr calendar failed: %s", exc)
            return []

    async def get_queue(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json("/api/v3/queue", params={"pageSize": 50})
            records = data.get("records", []) if isinstance(data, dict) else (data or [])
            return [
                {"source": "radarr", "icon": self.icon, "title": r.get("title", "?"),
                 "status": r.get("status"), "progress": _progress(r)}
                for r in records
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("radarr queue failed: %s", exc)
            return []

    async def add(self, term: str) -> Optional[str]:
        """Sucht einen Film und legt ihn zum Download an. Gibt den Titel zurück."""
        if not self.is_configured:
            return None
        try:
            results = await self._get_json("/api/v3/movie/lookup", params={"term": term})
            if not results:
                return None
            movie = results[0]
            qp = settings.radarr_quality_profile_id or await self._first("/api/v3/qualityprofile", "id")
            root = settings.radarr_root_folder or await self._first("/api/v3/rootfolder", "path")
            if not qp or not root:
                self.logger.warning("radarr add: kein qualityProfile/rootFolder verfügbar")
                return None
            payload = {
                **movie,
                "qualityProfileId": qp,
                "rootFolderPath": root,
                "monitored": True,
                "addOptions": {"searchForMovie": True},
            }
            await self._post_json("/api/v3/movie", payload)
            return movie.get("title")
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("radarr add failed: %s", exc)
            return None
