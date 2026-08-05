"""Admin-Endpunkte: Connector-Zugänge (URLs/Tokens) im UI verwalten.

Nur für Admins. Secrets werden **nie** im Klartext zurückgegeben (nur ``is_set``);
gespeicherte Werte greifen sofort (kein Neustart).
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.registry import registry
from app.core.database import get_db
from app.core.security import require_min_role
from app.models.user import ROLE_ADMIN, User
from app.services import config_store

router = APIRouter(prefix="/api/admin", tags=["admin"])


class SettingsUpdate(BaseModel):
    values: Dict[str, str]


def _view(group: Dict[str, Any]) -> Dict[str, Any]:
    fields = []
    for key, label, secret in group["fields"]:
        cur = getattr(settings, key, None) or ""
        fields.append({
            "key": key, "label": label, "secret": secret,
            "value": "" if secret else cur,   # Secrets NIE zurückgeben
            "is_set": bool(cur),
        })
    conn = registry.get(group["name"])
    return {
        "name": group["name"],
        "title": group["title"],
        "fields": fields,
        "configured": (conn.is_configured if conn else None),
    }


@router.get("/settings")
async def get_settings(current_user: User = Depends(require_min_role(ROLE_ADMIN))):
    """Alle editierbaren Connector-Zugänge (Secrets maskiert)."""
    return [_view(g) for g in config_store.CONNECTOR_SETTINGS]


@router.put("/settings")
async def update_settings(
    data: SettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_min_role(ROLE_ADMIN)),
):
    """Zugänge speichern (verschlüsselt) und sofort anwenden – kein Neustart."""
    config_store.save_overrides(db, data.values)
    return {"saved": True, "connectors": [_view(g) for g in config_store.CONNECTOR_SETTINGS]}
