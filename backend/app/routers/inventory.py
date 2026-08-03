"""Inventar-Endpunkte (Homebox)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/inventory", tags=["inventory"])


def _connector():
    c = registry.get("homebox")
    if not c:
        raise HTTPException(status_code=503, detail="Inventory connector unavailable")
    return c


@router.get("")
async def list_items(limit: int = 50, current_user: User = Depends(get_current_user)):
    return await _connector().get_items(limit=limit)


@router.get("/search")
async def search(q: str, limit: int = 10, current_user: User = Depends(get_current_user)):
    return await _connector().search(q, limit=limit)
