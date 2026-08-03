"""Dashboard – aggregierte Tagesübersicht.

Bündelt Wetter, Termine, Aufgaben, Einkauf, Pakete, Erinnerungen, Smart-Home
und proaktive Hinweise in einer einzigen, ausfallsicheren Antwort.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.connectors.registry import registry
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.package import Package
from app.models.reminder import Reminder
from app.models.user import User
from app.services.insights import generate_insights

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


async def _safe(coro, default):
    try:
        return await coro
    except Exception:  # noqa: BLE001
        return default


@router.get("")
async def get_dashboard(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    weather = registry.get("weather")
    calendar = registry.get("caldav")
    tasks = registry.get("vikunja")
    shopping = registry.get("kitchenowl")
    smarthome = registry.get("homeassistant")

    (
        weather_current,
        weather_forecast,
        events_today,
        events_upcoming,
        open_tasks,
        shopping_items,
        smart_overview,
        insights,
    ) = await asyncio.gather(
        _safe(weather.get_current(), {}) if weather else _noop({}),
        _safe(weather.get_forecast(5), []) if weather else _noop([]),
        _safe(calendar.get_today(), []) if calendar else _noop([]),
        _safe(calendar.get_events(7), []) if calendar else _noop([]),
        _safe(tasks.get_tasks(), []) if tasks else _noop([]),
        _safe(shopping.get_items(), []) if shopping else _noop([]),
        _safe(smarthome.get_overview(), {}) if smarthome else _noop({}),
        _safe(generate_insights(db), []),
    )

    # Lokale Daten (Hermes-eigene Speicher)
    reminders = (
        db.query(Reminder)
        .filter(Reminder.completed == False)  # noqa: E712
        .order_by(Reminder.due_at.is_(None), Reminder.due_at.asc())
        .limit(10)
        .all()
    )
    packages = db.query(Package).filter(Package.status != "delivered").all()

    return {
        "greeting": _greeting(current_user.full_name or current_user.username),
        "date": date.today().isoformat(),
        "weather": {"current": weather_current, "forecast": weather_forecast},
        "calendar": {"today": events_today, "upcoming": events_upcoming},
        "tasks": {"open_count": len(open_tasks), "items": open_tasks[:8]},
        "shopping": {"count": len(shopping_items), "items": shopping_items[:12]},
        "packages": [
            {
                "carrier": p.carrier,
                "description": p.description,
                "status": p.status,
                "expected_at": p.expected_at.isoformat() if p.expected_at else None,
            }
            for p in packages
        ],
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "due_at": r.due_at.isoformat() if r.due_at else None,
                "priority": r.priority,
            }
            for r in reminders
        ],
        "smarthome": smart_overview,
        "insights": insights,
    }


@router.get("/insights")
async def get_insights(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await generate_insights(db)


async def _noop(value):
    return value


def _greeting(name: str) -> str:
    hour = datetime.now().hour
    if hour < 11:
        prefix = "Guten Morgen"
    elif hour < 18:
        prefix = "Hallo"
    else:
        prefix = "Guten Abend"
    return f"{prefix}, {name}!"
