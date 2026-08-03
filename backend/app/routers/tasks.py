"""Aufgaben-Endpunkte (Vikunja)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.connectors.registry import registry
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class CreateTaskRequest(BaseModel):
    title: str
    description: str = ""
    due_date: Optional[str] = None
    priority: Optional[int] = None


def _connector():
    c = registry.get("vikunja")
    if not c:
        raise HTTPException(status_code=503, detail="Tasks connector unavailable")
    return c


@router.get("")
async def list_tasks(include_done: bool = False, current_user: User = Depends(get_current_user)):
    return await _connector().get_tasks(include_done=include_done)


@router.post("")
async def create_task(data: CreateTaskRequest, current_user: User = Depends(get_current_user)):
    result = await _connector().create_task(
        title=data.title, description=data.description, due_date=data.due_date, priority=data.priority
    )
    if not result:
        raise HTTPException(status_code=502, detail="Could not create task (connector not configured or error)")
    return result
