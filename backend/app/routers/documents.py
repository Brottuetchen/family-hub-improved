"""Dokumenten-Endpunkte (Paperless-ngx)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _connector():
    c = registry.get("paperless")
    if not c:
        raise HTTPException(status_code=503, detail="Documents connector unavailable")
    return c


@router.get("/recent")
async def recent(limit: int = 10, current_user: User = Depends(get_current_user)):
    return await _connector().get_recent(limit=limit)


@router.get("/search")
async def search(q: str, limit: int = 10, current_user: User = Depends(get_current_user)):
    return await _connector().search(q, limit=limit)
