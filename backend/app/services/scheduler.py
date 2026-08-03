"""Hintergrund-Scheduler.

Prüft periodisch fällige Erinnerungen und verschickt dafür Web-Push-
Benachrichtigungen (einmalig, danach als ``notified`` markiert). Läuft als
asyncio-Task im App-Lifespan.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from app.core.database import SessionLocal
from app.core.logging_config import get_logger
from app.models.reminder import Reminder
from app.services.notifications import notification_service
from app.services.recurrence import advance

logger = get_logger("service.scheduler")

# Prüfintervall in Sekunden.
CHECK_INTERVAL = 60


async def _tick() -> None:
    """Ein Prüf-Durchlauf: fällige, nicht benachrichtigte Erinnerungen pushen."""
    db = SessionLocal()
    try:
        now = datetime.now()
        due = (
            db.query(Reminder)
            .filter(
                Reminder.completed == False,  # noqa: E712
                Reminder.notified == False,  # noqa: E712
                Reminder.due_at != None,  # noqa: E711
                Reminder.due_at <= now,
            )
            .all()
        )
        if not due:
            return
        for reminder in due:
            if notification_service.is_configured:
                await asyncio.to_thread(
                    notification_service.send_to_all,
                    db,
                    "⏰ Erinnerung",
                    reminder.title,
                    "/",
                    "/assets/icons/app-icon-192.png",
                    reminder.priority or "info",
                )
            # Wiederkehrende Erinnerung: nächste Fälligkeit planen statt abschließen.
            next_due = advance(reminder.due_at, reminder.recurrence)
            if next_due:
                reminder.due_at = next_due
                reminder.notified = False
                reminder.completed = False
            else:
                reminder.notified = True
        db.commit()
        logger.info("scheduler: notified %d due reminder(s)", len(due))
    except Exception as exc:  # noqa: BLE001
        logger.warning("scheduler tick failed: %s", exc)
    finally:
        db.close()


async def run_scheduler() -> None:
    """Endlosschleife – wird beim Shutdown via CancelledError beendet."""
    logger.info("reminder scheduler started (interval=%ds)", CHECK_INTERVAL)
    try:
        while True:
            await asyncio.sleep(CHECK_INTERVAL)
            await _tick()
    except asyncio.CancelledError:  # pragma: no cover
        logger.info("reminder scheduler stopped")
        raise
