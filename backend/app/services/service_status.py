"""Generisches Homelab-Status-Board.

Prüft eine konfigurierbare Liste beliebiger Dienste (``HOMELAB_SERVICES``) auf
Erreichbarkeit (up/down) – der Nachbau des alten „Services-Status"-Boards für
Dienste ohne tiefe Integration (SABnzbd, Immich, Trilium, Nextcloud …).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import httpx

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("service.status")


async def _probe_one(client: httpx.AsyncClient, svc: Dict[str, str]) -> Dict[str, Any]:
    result = {**svc, "status": "offline"}
    try:
        resp = await client.get(svc["url"])
        result["status"] = "online" if resp.status_code < 500 else "error"
    except Exception as exc:  # noqa: BLE001
        logger.debug("service %s offline: %s", svc.get("name"), exc)
        result["status"] = "offline"
    return result


async def probe_services() -> List[Dict[str, Any]]:
    """up/down-Status aller konfigurierten Homelab-Dienste (parallel)."""
    services = settings.homelab_service_list
    if not services:
        return []
    async with httpx.AsyncClient(timeout=4.0, verify=settings.verify_tls, follow_redirects=True) as client:
        return list(await asyncio.gather(*(_probe_one(client, s) for s in services)))
