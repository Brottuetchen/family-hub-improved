"""Connector-Registry.

Zentrale Verwaltung aller Connectors: Instanziierung (Singletons), Lookup nach
Name/Kategorie, aggregierte Health-Checks und globale Suche.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from app.connectors.audiobookshelf_connector import AudiobookshelfConnector
from app.connectors.base import BaseConnector
from app.connectors.caldav_connector import CalDAVConnector
from app.connectors.homeassistant_connector import HomeAssistantConnector
from app.connectors.homebox_connector import HomeboxConnector
from app.connectors.kitchenowl_connector import KitchenOwlConnector
from app.connectors.overseerr_connector import OverseerrConnector
from app.connectors.paperless_connector import PaperlessConnector
from app.connectors.plex_connector import PlexConnector
from app.connectors.radarr_connector import RadarrConnector
from app.connectors.sonarr_connector import SonarrConnector
from app.connectors.teddycloud_connector import TeddyCloudConnector
from app.connectors.vikunja_connector import VikunjaConnector
from app.connectors.weather_connector import WeatherConnector


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: Dict[str, BaseConnector] = {}
        for connector_cls in (
            WeatherConnector,
            CalDAVConnector,
            VikunjaConnector,
            KitchenOwlConnector,
            PaperlessConnector,
            HomeboxConnector,
            HomeAssistantConnector,
            PlexConnector,
            AudiobookshelfConnector,
            TeddyCloudConnector,
            OverseerrConnector,
            SonarrConnector,
            RadarrConnector,
        ):
            instance = connector_cls()
            self._connectors[instance.name] = instance

    # --- Lookup ---

    def get(self, name: str) -> Optional[BaseConnector]:
        return self._connectors.get(name)

    def by_category(self, category: str) -> Optional[BaseConnector]:
        for c in self._connectors.values():
            if c.category == category:
                return c
        return None

    def all(self) -> List[BaseConnector]:
        return list(self._connectors.values())

    # --- Aggregierte Operationen ---

    async def health_all(self) -> List[Dict[str, Any]]:
        """Parallele Health-Checks aller Connectors."""
        connectors = self.all()
        results = await asyncio.gather(*(c.health() for c in connectors), return_exceptions=True)
        out: List[Dict[str, Any]] = []
        for connector, res in zip(connectors, results):
            base = connector.info()
            if isinstance(res, Exception):
                base.update({"status": "error", "detail": str(res)})
            else:
                base.update(res)
            out.append(base)
        return out

    async def search_all(self, query: str, limit_per_source: int = 5) -> List[Dict[str, Any]]:
        """Globale Suche über alle suchfähigen, konfigurierten Connectors."""
        connectors = [c for c in self.all() if c.is_configured]

        async def _safe_search(c: BaseConnector) -> List[Dict[str, Any]]:
            try:
                return await c.search(query, limit=limit_per_source)
            except Exception:  # noqa: BLE001
                return []

        grouped = await asyncio.gather(*(_safe_search(c) for c in connectors))
        results: List[Dict[str, Any]] = []
        for group in grouped:
            results.extend(group)
        return results


# Singleton-Instanz
registry = ConnectorRegistry()


def get_registry() -> ConnectorRegistry:
    return registry
