"""Proaktive Insights – "Hermes denkt mit".

Aggregiert Signale aus Connectors und der Datenbank zu handlungsorientierten
Vorschlägen, z.B.:
  * "Morgen regnet es → Fahrradfahrt absagen?"
  * "Paket wird heute geliefert."
  * "Carina hat in 5 Tagen Geburtstag → Geschenkideen sammeln?"
  * fällige Erinnerungen (Müll rausbringen, ...).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.connectors.registry import registry
from app.core.logging_config import get_logger
from app.models.family import FamilyMember
from app.models.package import Package
from app.models.reminder import Reminder

logger = get_logger("service.insights")


async def generate_insights(db: Session) -> List[Dict[str, Any]]:
    insights: List[Dict[str, Any]] = []
    insights.extend(_reminder_insights(db))
    insights.extend(_package_insights(db))
    insights.extend(_birthday_insights(db))
    insights.extend(await _weather_insights())

    priority_rank = {"critical": 0, "important": 1, "info": 2}
    insights.sort(key=lambda i: priority_rank.get(i.get("priority", "info"), 3))
    return insights


def _reminder_insights(db: Session) -> List[Dict[str, Any]]:
    now = datetime.now()
    horizon = now + timedelta(hours=18)
    due = (
        db.query(Reminder)
        .filter(Reminder.completed == False, Reminder.due_at != None)  # noqa: E711,E712
        .filter(Reminder.due_at <= horizon)
        .order_by(Reminder.due_at.asc())
        .limit(10)
        .all()
    )
    out = []
    for r in due:
        out.append(
            {
                "type": "reminder",
                "priority": r.priority or "info",
                "title": r.title,
                "message": _humanize_due(r.due_at),
                "icon": "⏰",
                "action": None,
            }
        )
    return out


def _package_insights(db: Session) -> List[Dict[str, Any]]:
    today = date.today()
    packages = (
        db.query(Package)
        .filter(Package.status != "delivered")
        .all()
    )
    out = []
    for p in packages:
        arriving_today = p.expected_at and p.expected_at.date() == today
        if arriving_today or p.status == "out_for_delivery":
            out.append(
                {
                    "type": "package",
                    "priority": "important",
                    "title": f"{p.carrier.upper()}-Paket unterwegs",
                    "message": (p.description or "Lieferung heute erwartet"),
                    "icon": "📦",
                    "action": None,
                }
            )
    return out


def _birthday_insights(db: Session) -> List[Dict[str, Any]]:
    today = date.today()
    members = db.query(FamilyMember).filter(FamilyMember.birthday != None).all()  # noqa: E711
    out = []
    for m in members:
        days = _days_until_birthday(m.birthday, today)
        if days is None or days > 14:
            continue
        if days == 0:
            msg = f"{m.name} hat heute Geburtstag! 🎉"
        else:
            msg = f"{m.name} hat in {days} Tagen Geburtstag → Geschenkideen sammeln?"
        out.append(
            {
                "type": "birthday",
                "priority": "important" if days <= 3 else "info",
                "title": "Geburtstag",
                "message": msg,
                "icon": "🎂",
                "action": None,
            }
        )
    return out


async def _weather_insights() -> List[Dict[str, Any]]:
    weather = registry.get("weather")
    if not weather or not weather.is_configured:
        return []
    try:
        rain = await weather.will_rain_tomorrow()  # type: ignore[attr-defined]
        if rain:
            return [
                {
                    "type": "weather",
                    "priority": "info",
                    "title": "Morgen regnet es",
                    "message": "Outdoor-Pläne prüfen (z.B. Fahrradfahrt absagen?).",
                    "icon": "🌧️",
                    "action": None,
                }
            ]
    except Exception as exc:  # noqa: BLE001
        logger.debug("weather insight failed: %s", exc)
    return []


# --- Helpers ---

def _humanize_due(due_at: Optional[datetime]) -> str:
    if not due_at:
        return "Fällig"
    now = datetime.now()
    delta = due_at - now
    if delta.total_seconds() < 0:
        return "Überfällig"
    hours = int(delta.total_seconds() // 3600)
    if hours < 1:
        return "In weniger als 1 Stunde fällig"
    if hours < 24:
        return f"Heute fällig ({due_at.strftime('%H:%M')})"
    return f"Fällig am {due_at.strftime('%d.%m. %H:%M')}"


def _days_until_birthday(birthday: str, today: date) -> Optional[int]:
    try:
        parts = birthday.split("-")
        month, day = int(parts[-2]), int(parts[-1])
        next_bday = date(today.year, month, day)
        if next_bday < today:
            next_bday = date(today.year + 1, month, day)
        return (next_bday - today).days
    except (ValueError, IndexError):
        return None
