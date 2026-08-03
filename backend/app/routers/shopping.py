"""Einkaufslisten-Endpunkte (KitchenOwl)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/shopping", tags=["shopping"])


class AddItemRequest(BaseModel):
    name: str
    list_id: Optional[int] = None


def _connector():
    c = registry.get("kitchenowl")
    if not c:
        raise HTTPException(status_code=503, detail="Shopping connector unavailable")
    return c


@router.get("")
async def list_items(current_user: User = Depends(get_current_user)):
    return await _connector().get_items()


@router.post("")
async def add_item(data: AddItemRequest, current_user: User = Depends(get_current_user)):
    result = await _connector().add_item(data.name, list_id=data.list_id)
    if not result:
        raise HTTPException(status_code=502, detail="Could not add item (connector not configured or error)")
    return result
