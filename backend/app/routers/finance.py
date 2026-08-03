"""Finanzen – Übersicht laufender Kosten (Phase 2, Grundgerüst).

Aktuell werden Erinnerungen mit Finanzbezug als "anstehende Zahlungen"
interpretiert. Eine echte Bank-/Vertragsintegration folgt in einer späteren
Phase; die Struktur ist bereits vorbereitet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.reminder import Reminder
from app.models.user import User

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/overview")
async def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    upcoming = (
        db.query(Reminder)
        .filter(Reminder.completed == False)  # noqa: E712
        .filter(Reminder.due_at != None)  # noqa: E711
        .filter(Reminder.due_at >= datetime.now())
        .order_by(Reminder.due_at.asc())
        .limit(20)
        .all()
    )
    payments = [
        {"title": r.title, "due_at": r.due_at.isoformat() if r.due_at else None}
        for r in upcoming
        if any(k in (r.title or "").lower() for k in ("rechnung", "zahlung", "beitrag", "miete", "versicherung"))
    ]
    return {
        "note": "Finanz-Modul im Aufbau (Phase 2). Bank-/Vertragsintegration folgt.",
        "upcoming_payments": payments,
        "recurring": [],
        "budgets": [],
    }
