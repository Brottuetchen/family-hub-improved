"""Kalender-Connector via CalDAV (Nextcloud, iCloud, Radicale, ...).

Unterstützt gemeinsame Familienkalender inkl. Farbcodierung. Zusätzliche
Kalender (Feiertage, Ferien, Müllkalender) werden automatisch mitgelesen,
sofern sie im CalDAV-Server abonniert sind.

Die ``caldav``-Bibliothek arbeitet synchron; die Aufrufe werden daher in einem
Thread ausgeführt, um den async Event-Loop nicht zu blockieren.
"""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class CalDAVConnector(BaseConnector):
    name = "caldav"
    display_name = "Kalender (CalDAV/Nextcloud)"
    category = "calendar"
    icon = "📅"

    @property
    def is_configured(self) -> bool:
        return bool(settings.caldav_url and settings.caldav_username and settings.caldav_password)

    @property
    def base_url(self) -> Optional[str]:
        return settings.caldav_url

    async def _probe(self) -> bool:
        events = await self.get_events(days_ahead=1)
        # Erfolgreiche (auch leere) Antwort bedeutet: erreichbar.
        return events is not None

    async def get_events(
        self, days_ahead: int = 7, start: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Termine im angegebenen Zeitfenster (Standard: nächste 7 Tage)."""
        if not self.is_configured:
            return []
        start = start or datetime.now()
        end = start + timedelta(days=days_ahead)
        try:
            return await asyncio.to_thread(self._fetch_events_sync, start, end)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("caldav get_events failed: %s", exc)
            return []

    async def get_today(self) -> List[Dict[str, Any]]:
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        events = await self.get_events(days_ahead=1, start=today)
        end = today + timedelta(days=1)
        return [e for e in events if _event_on_day(e, today, end)]

    # --- Synchrone CalDAV-Logik (läuft im Thread) ---

    def _fetch_events_sync(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        try:
            import caldav  # lazy import – optionaler Dependency
        except ImportError:
            self.logger.warning("python 'caldav' package not installed – calendar disabled")
            return []

        client = caldav.DAVClient(
            url=settings.caldav_url,
            username=settings.caldav_username,
            password=settings.caldav_password,
            ssl_verify_cert=settings.verify_tls,
        )
        principal = client.principal()
        results: List[Dict[str, Any]] = []

        for calendar in principal.calendars():
            cal_name = _safe(lambda: str(calendar.name)) or "Kalender"
            cal_color = _safe(lambda: str(calendar.get_property(_color_prop())))
            try:
                found = calendar.search(start=start, end=end, event=True, expand=True)
            except Exception:  # noqa: BLE001
                # Nicht alle Server unterstützen expand/search identisch.
                found = calendar.date_search(start=start, end=end)

            for ev in found:
                comp = _safe(lambda: ev.icalendar_component)
                if comp is None:
                    continue
                results.append(_component_to_event(comp, cal_name, cal_color))

        results.sort(key=lambda e: e.get("start") or "")
        return results


# --- Hilfsfunktionen ---

def _color_prop():
    try:
        import caldav

        return caldav.elements.ical.CalendarColor()
    except Exception:  # noqa: BLE001
        return None


def _component_to_event(comp: Any, cal_name: str, cal_color: Optional[str]) -> Dict[str, Any]:
    summary = str(comp.get("summary", "Termin"))
    dtstart = comp.get("dtstart")
    dtend = comp.get("dtend")
    start_val = getattr(dtstart, "dt", None)
    end_val = getattr(dtend, "dt", None)
    all_day = isinstance(start_val, date) and not isinstance(start_val, datetime)
    return {
        "title": summary,
        "start": _iso(start_val),
        "end": _iso(end_val),
        "all_day": all_day,
        "location": str(comp.get("location", "")) or None,
        "calendar": cal_name,
        "color": cal_color or "#4f46e5",
    }


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _event_on_day(event: Dict[str, Any], day_start: datetime, day_end: datetime) -> bool:
    start = event.get("start")
    if not start:
        return False
    try:
        s = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        s = s.replace(tzinfo=None)
    except ValueError:
        try:
            s = datetime.combine(date.fromisoformat(str(start)), datetime.min.time())
        except ValueError:
            return False
    return day_start <= s < day_end


def _safe(fn):
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return None
