"""Kalender-Endpunkte (CalDAV/Nextcloud)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User
from app.services.holidays import upcoming_holidays

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _connector():
    c = registry.get("caldav")
    if not c:
        raise HTTPException(status_code=503, detail="Calendar connector unavailable")
    return c


@router.get("/today")
async def today(current_user: User = Depends(get_current_user)):
    return await _connector().get_today()


@router.get("/events")
async def events(days: int = 7, current_user: User = Depends(get_current_user)):
    return await _connector().get_events(days_ahead=days)


@router.get("/holidays")
async def holidays(days: int = 60, current_user: User = Depends(get_current_user)):
    """Deutsche Feiertage (bundesweit) in den nächsten Tagen."""
    return upcoming_holidays(days=days)
