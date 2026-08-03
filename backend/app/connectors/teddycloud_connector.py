"""Tonie-Connector für TeddyCloud (https://tonies.github.io/teddycloud/).

Erkennt aktuell abgespielte Tonies je Toniebox (kein Auth-Token nötig).
Portiert aus dem Legacy Family Hub, defensiv gegen API-Varianten abgesichert.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector

# Nur Tonies anzeigen, die in den letzten 30 Minuten liefen.
RECENT_SECONDS = 1800


class TeddyCloudConnector(BaseConnector):
    name = "teddycloud"
    display_name = "Tonies (TeddyCloud)"
    category = "media"
    icon = "🧸"

    @property
    def is_configured(self) -> bool:
        return bool(settings.teddycloud_url)

    @property
    def base_url(self) -> Optional[str]:
        return settings.teddycloud_url

    async def _probe(self) -> bool:
        async with self._client() as client:
            resp = await client.get("/api/getBoxes")
            return resp.status_code < 500

    async def _text(self, client, path: str) -> Optional[str]:
        try:
            resp = await client.get(path)
            if resp.status_code == 200:
                return resp.text.strip()
        except Exception:  # noqa: BLE001
            return None
        return None

    async def get_active_tonies(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        out: List[Dict[str, Any]] = []
        try:
            async with self._client() as client:
                boxes_resp = await client.get("/api/getBoxes")
                boxes_resp.raise_for_status()
                boxes = (boxes_resp.json() or {}).get("boxes", [])

                for box in boxes:
                    box_id = box.get("ID")
                    if not box_id:
                        continue
                    last_ruid = await self._text(client, f"/api/settings/get/internal.last_ruid?overlay={box_id}")
                    if not last_ruid or last_ruid.startswith("0000000"):
                        continue
                    last_time = await self._text(client, f"/api/settings/get/internal.last_ruid_time?overlay={box_id}")
                    try:
                        if last_time and (int(time.time()) - int(last_time)) > RECENT_SECONDS:
                            continue
                    except ValueError:
                        pass

                    tag_resp = await client.get(f"/api/getTagIndex?overlay={box_id}")
                    if tag_resp.status_code != 200:
                        continue
                    for tag in (tag_resp.json() or {}).get("tags", []):
                        if tag.get("ruid") != last_ruid:
                            continue
                        info = tag.get("tonieInfo", {}) or {}
                        series, episode = info.get("series", ""), info.get("episode", "")
                        title = episode or series or "Unbekannter Tonie"
                        subtitle = series if (series and episode and series != episode) else None
                        picture = info.get("picture", "")
                        out.append(
                            {
                                "source": "teddycloud",
                                "title": title,
                                "subtitle": subtitle,
                                "type": "tonie",
                                "user": box.get("boxName", "Toniebox"),
                                "thumb": picture if picture and not picture.endswith("/img_unknown.png") else None,
                                "icon": "🧸",
                            }
                        )
                        break
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("teddycloud active tonies failed: %s", exc)
        return out
