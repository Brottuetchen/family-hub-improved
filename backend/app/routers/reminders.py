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
from app.services.recurrence import VALID_RECURRENCE, advance

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


class ReminderRequest(BaseModel):
    title: str
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str = "info"
    recurrence: str = "none"
    family_member_id: Optional[int] = None


class ReminderUpdate(BaseModel):
    title: Optional[str] = None
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[str] = None
    recurrence: Optional[str] = None
    completed: Optional[bool] = None


class ReminderResponse(BaseModel):
    id: int
    title: str
    notes: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: str
    recurrence: str
    completed: bool
    source: str

    model_config = ConfigDict(from_attributes=True)


def _validate_recurrence(value: Optional[str]) -> None:
    if value is not None and value not in VALID_RECURRENCE:
        raise HTTPException(status_code=400, detail=f"Invalid recurrence. Valid: {', '.join(sorted(VALID_RECURRENCE))}")


@router.get("", response_model=list[ReminderResponse])
async def list_reminders(include_completed: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Reminder)
    if not include_completed:
        query = query.filter(Reminder.completed == False)  # noqa: E712
    return query.order_by(Reminder.due_at.is_(None), Reminder.due_at.asc()).all()


@router.post("", response_model=ReminderResponse)
async def create_reminder(data: ReminderRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _validate_recurrence(data.recurrence)
    reminder = Reminder(
        title=data.title,
        notes=data.notes,
        due_at=data.due_at,
        priority=data.priority,
        recurrence=data.recurrence,
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
    _validate_recurrence(data.recurrence)

    updates = data.model_dump(exclude_unset=True)
    # Eine wiederkehrende Erinnerung "abhaken" heißt: zum nächsten Termin rollen.
    if updates.get("completed") is True and (updates.get("recurrence", reminder.recurrence) or "none") != "none":
        next_due = advance(reminder.due_at, updates.get("recurrence", reminder.recurrence))
        if next_due:
            reminder.due_at = next_due
            reminder.notified = False
            updates["completed"] = False
    for key, value in updates.items():
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
