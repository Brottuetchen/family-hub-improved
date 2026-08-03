"""Medien-Endpunkte: Plex, Audiobookshelf, Tonies (TeddyCloud), Overseerr."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/media", tags=["media"])


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


async def _noop(v):
    return v
