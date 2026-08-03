"""Medien-Endpunkte (Plex) – optionales Legacy-Modul."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/media", tags=["media"])


def _connector():
    c = registry.get("plex")
    if not c:
        raise HTTPException(status_code=503, detail="Media connector unavailable")
    return c


@router.get("/streams")
async def active_streams(current_user: User = Depends(get_current_user)):
    return await _connector().get_active_streams()


@router.get("/recent")
async def recent(limit: int = 5, current_user: User = Depends(get_current_user)):
    return await _connector().get_recent(limit=limit)
