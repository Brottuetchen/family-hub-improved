"""Smart-Home-Connector für Home Assistant (https://www.home-assistant.io).

Steuerung von Licht, Heizung, Kameras, Türen und Sensoren sowie eine
verdichtete Übersicht für das Dashboard ("Familienstatus", Energie, offene Türen).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class HomeAssistantConnector(BaseConnector):
    name = "homeassistant"
    display_name = "Smart Home (Home Assistant)"
    category = "smarthome"
    icon = "🏠"

    @property
    def is_configured(self) -> bool:
        return bool(settings.homeassistant_url and settings.homeassistant_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.homeassistant_url

    def _auth_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {settings.homeassistant_token}",
            "Content-Type": "application/json",
        }

    async def _probe(self) -> bool:
        data = await self._get_json("/api/")
        return isinstance(data, dict)

    async def get_states(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Alle Entitäts-Zustände (optional nach Domain gefiltert)."""
        if not self.is_configured:
            return []
        try:
            states = await self._get_json("/api/states")
            if not isinstance(states, list):
                return []
            if domain:
                states = [s for s in states if str(s.get("entity_id", "")).startswith(f"{domain}.")]
            return [
                {
                    "entity_id": s.get("entity_id"),
                    "state": s.get("state"),
                    "name": (s.get("attributes") or {}).get("friendly_name", s.get("entity_id")),
                    "attributes": s.get("attributes", {}),
                }
                for s in states
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("homeassistant get_states failed: %s", exc)
            return []

    async def get_overview(self) -> Dict[str, Any]:
        """Verdichtete Smart-Home-Übersicht fürs Dashboard."""
        if not self.is_configured:
            return {}
        states = await self.get_states()
        lights_on = [s for s in states if s["entity_id"].startswith("light.") and s["state"] == "on"]
        doors_open = [
            s
            for s in states
            if s["entity_id"].startswith("binary_sensor.")
            and (s["attributes"].get("device_class") in {"door", "window"})
            and s["state"] == "on"
        ]
        temps = [
            s
            for s in states
            if s["entity_id"].startswith("sensor.")
            and s["attributes"].get("device_class") == "temperature"
        ]
        return {
            "lights_on": len(lights_on),
            "doors_windows_open": len(doors_open),
            "open_entities": [d["name"] for d in doors_open],
            "temperature_sensors": [
                {"name": t["name"], "value": t["state"], "unit": t["attributes"].get("unit_of_measurement")}
                for t in temps[:5]
            ],
        }

    async def call_service(self, domain: str, service: str, entity_id: str) -> bool:
        """Ruft einen HA-Service auf (z.B. light.turn_on)."""
        if not self.is_configured:
            return False
        try:
            async with self._client() as client:
                resp = await client.post(
                    f"/api/services/{domain}/{service}", json={"entity_id": entity_id}
                )
                resp.raise_for_status()
                return True
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("homeassistant call_service failed: %s", exc)
            return False
