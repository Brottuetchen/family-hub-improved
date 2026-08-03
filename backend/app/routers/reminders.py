"""Erinnerungen (Hermes-eigener Speicher)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.reminder import Reminder
from app.models.user import User

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class ReminderRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str = "info"
    family_member_id: Optional[int] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[str] = None
    completed: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: int
    title: str
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str
    completed: bool
    source: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(include_completed: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Reminder)
    if not include_completed:
        query = query.filter(Reminder.completed == False)  # noqa: E712
    return query.order_by(Reminder.due_at.is_(None), Reminder.due_at.asc()).all()


@router.post("", response_model=ReminderResponse)
async def create_reminder(data: ReminderRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reminder = Reminder(
        title=data.title,
        notes=data.notes,
        due_at=data.due_at,
        priority=data.priority,
        family_member_id=data.family_member_id,
        source="user",
        created_by=current_user.id,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.patch("/{reminder_id}", response_model=ReminderResponse)
async def update_reminder(reminder_id: int, data: ReminderUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(reminder, key, value)
    db.commit()
    db.refresh(reminder)
    return reminder


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reminder = db.query(Reminder).filter(Reminder.id == reminder_id).first()
    if not reminder:
        raise HTTPException(status_code=404, detail="Reminder not found")
    db.delete(reminder)
    db.commit()
    return {"message": "deleted"}
