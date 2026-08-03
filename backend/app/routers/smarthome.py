"""Smart-Home-Endpunkte (Home Assistant)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.registry import registry
from app.core.security import get_current_user, require_min_role
from app.models.user import ROLE_PARTNER, User

router = APIRouter(prefix="/api/smarthome", tags=["smarthome"])


class ServiceCallRequest(BaseModel):
    domain: str
    service: str
    entity_id: str


def _connector():
    c = registry.get("homeassistant")
    if not c:
        raise HTTPException(status_code=503, detail="Smart home connector unavailable")
    return c


@router.get("/overview")
async def overview(current_user: User = Depends(get_current_user)):
    return await _connector().get_overview()


@router.get("/states")
async def states(domain: Optional[str] = None, current_user: User = Depends(get_current_user)):
    return await _connector().get_states(domain=domain)


@router.post("/service")
async def call_service(data: ServiceCallRequest, current_user: User = Depends(require_min_role(ROLE_PARTNER))):
    ok = await _connector().call_service(data.domain, data.service, data.entity_id)
    if not ok:
        raise HTTPException(status_code=502, detail="Service call failed")
    return {"success": True}
