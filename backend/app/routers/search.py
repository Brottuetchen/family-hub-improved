"""Globale Suche über alle Connectors."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("")
async def search(q: str, current_user: User = Depends(get_current_user)):
    """Sucht gleichzeitig in Paperless, Vikunja, Homebox, ... – eine Suche findet alles."""
    results = await registry.search_all(q)
    return {"query": q, "count": len(results), "results": results}
