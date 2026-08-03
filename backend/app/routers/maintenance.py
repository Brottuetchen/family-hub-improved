"""Wartungspläne (Auto, Haus, Garten, Geräte)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.maintenance import MaintenanceTask
from app.models.user import User

router = APIRouter(prefix="/api/maintenance", tags=["maintenance"])


class MaintenanceRequest(BaseModel):
    title: str
    description: Optional[str] = None
    category: str = "other"
    interval_days: Optional[int] = None
    last_done: Optional[date] = None
    next_due: Optional[date] = None
    family_member_id: Optional[int] = None


class MaintenanceResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: str
    interval_days: Optional[int] = None
    last_done: Optional[date] = None
    next_due: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


def _auto_next_due(data: MaintenanceRequest) -> Optional[date]:
    if data.next_due:
        return data.next_due
    if data.last_done and data.interval_days:
        return data.last_done + timedelta(days=data.interval_days)
    return None


@router.get("", response_model=list[MaintenanceResponse])
async def list_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(MaintenanceTask).order_by(MaintenanceTask.next_due.is_(None), MaintenanceTask.next_due.asc()).all()


@router.post("", response_model=MaintenanceResponse)
async def create_task(data: MaintenanceRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payload = data.model_dump()
    payload["next_due"] = _auto_next_due(data)
    task = MaintenanceTask(**payload)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/done", response_model=MaintenanceResponse)
async def mark_done(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Markiert eine Wartung als heute erledigt und plant die nächste Fälligkeit."""
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.last_done = date.today()
    if task.interval_days:
        task.next_due = date.today() + timedelta(days=task.interval_days)
    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}")
async def delete_task(task_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "deleted"}
