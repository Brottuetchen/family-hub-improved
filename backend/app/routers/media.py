"""Medien-Endpunkte: Plex, Audiobookshelf, Tonies (TeddyCloud), Overseerr."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.registry import registry
from app.core.security import get_current_user, require_min_role
from app.models.user import ROLE_PARTNER, User

router = APIRouter(prefix="/api/media", tags=["media"])


class AddMediaRequest(BaseModel):
    query: str


def _plex():
    c = registry.get("plex")
    if not c:
        raise HTTPException(status_code=503, detail="Media connector unavailable")
    return c


async def _safe(coro, default):
    try:
        return await coro
    except Exception:  # noqa: BLE001
        return default


@router.get("/streams")
async def active_streams(current_user: User = Depends(get_current_user)):
    return await _plex().get_active_streams()


@router.get("/recent")
async def recent(limit: int = 5, current_user: User = Depends(get_current_user)):
    return await _plex().get_recent(limit=limit)


@router.get("/now-playing")
async def now_playing(current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Was läuft gerade in der Familie – Plex, Hörbücher und Tonies vereint."""
    plex = registry.get("plex")
    abs_ = registry.get("audiobookshelf")
    teddy = registry.get("teddycloud")

    plex_streams, audio, tonies = await asyncio.gather(
        _safe(plex.get_active_streams(), []) if plex else _noop([]),
        _safe(abs_.get_active_sessions(), []) if abs_ else _noop([]),
        _safe(teddy.get_active_tonies(), []) if teddy else _noop([]),
    )

    streams: List[Dict[str, Any]] = []
    for s in plex_streams:
        streams.append({
            "source": "plex", "icon": "🎬",
            "title": s.get("title"), "subtitle": s.get("show", ""),
            "user": s.get("user"),
        })
    streams.extend(audio)
    streams.extend(tonies)
    return {"count": len(streams), "streams": streams}


@router.get("/requests")
async def requests(current_user: User = Depends(get_current_user)):
    """Offene Media-Anfragen (Overseerr)."""
    c = registry.get("overseerr")
    if not c:
        return []
    return await c.get_pending_requests()


@router.get("/upcoming")
async def upcoming(days: int = 14, current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Anstehende Serien-Folgen (Sonarr) und Film-Releases (Radarr), zusammengeführt."""
    items: List[Dict[str, Any]] = []
    for key in ("sonarr", "radarr"):
        c = registry.get(key)
        if c and c.is_configured:
            items.extend(await _safe(c.get_upcoming(days), []))
    items.sort(key=lambda i: i.get("date") or "")
    return items


@router.get("/queue")
async def download_queue(current_user: User = Depends(get_current_user)) -> List[Dict[str, Any]]:
    """Laufende Downloads (Sonarr + Radarr)."""
    items: List[Dict[str, Any]] = []
    for key in ("sonarr", "radarr"):
        c = registry.get(key)
        if c and c.is_configured:
            items.extend(await _safe(c.get_queue(), []))
    return items


@router.post("/series")
async def add_series(data: AddMediaRequest, current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    """Serie über Sonarr suchen und zum Download anlegen (ab Rolle partner)."""
    c = registry.get("sonarr")
    if not c or not c.is_configured:
        raise HTTPException(status_code=503, detail="Sonarr ist nicht konfiguriert.")
    title = await c.add(data.query)
    if not title:
        raise HTTPException(status_code=502, detail="Serie nicht gefunden oder Anlegen fehlgeschlagen.")
    return {"success": True, "title": title}


@router.post("/movie")
async def add_movie(data: AddMediaRequest, current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    """Film über Radarr suchen und zum Download anlegen (ab Rolle partner)."""
    c = registry.get("radarr")
    if not c or not c.is_configured:
        raise HTTPException(status_code=503, detail="Radarr ist nicht konfiguriert.")
    title = await c.add(data.query)
    if not title:
        raise HTTPException(status_code=502, detail="Film nicht gefunden oder Anlegen fehlgeschlagen.")
    return {"success": True, "title": title}


async def _noop(v):
    return v
