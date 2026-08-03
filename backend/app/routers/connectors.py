"""Connector-Status & Übersicht."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/connectors", tags=["connectors"])


@router.get("")
async def list_connectors(current_user: User = Depends(get_current_user)):
    """Metadaten + Konfigurationsstatus aller Connectors."""
    return [c.info() for c in registry.all()]


@router.get("/health")
async def health(current_user: User = Depends(get_current_user)):
    """Live-Erreichbarkeit aller Fachsysteme (parallel geprüft)."""
    return await registry.health_all()
