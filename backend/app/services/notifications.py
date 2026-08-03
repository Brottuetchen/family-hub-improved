"""Push-Notification-Service (Web Push / VAPID).

Persistiert Subscriptions in der Datenbank und verschickt Benachrichtigungen
mit Prioritäten (kritisch | wichtig | info). Ungültige Subscriptions (410/404)
werden automatisch entfernt.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.logging_config import get_logger
from app.models.notification import PushSubscriptionRecord

logger = get_logger("service.notifications")

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # pragma: no cover
    webpush = None
    WebPushException = Exception


class NotificationService:
    @property
    def is_configured(self) -> bool:
        return bool(settings.vapid_private_key and settings.vapid_public_key and webpush)

    @property
    def public_key(self) -> Optional[str]:
        return settings.vapid_public_key

    # --- Subscriptions ---

    def add_subscription(
        self,
        db: Session,
        endpoint: str,
        keys: Dict[str, str],
        user_agent: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> PushSubscriptionRecord:
        existing = (
            db.query(PushSubscriptionRecord)
            .filter(PushSubscriptionRecord.endpoint == endpoint)
            .first()
        )
        if existing:
            existing.keys_json = json.dumps(keys)
            db.commit()
            return existing
        record = PushSubscriptionRecord(
            endpoint=endpoint,
            keys_json=json.dumps(keys),
            user_agent=user_agent,
            user_id=user_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    def list_subscriptions(self, db: Session) -> List[PushSubscriptionRecord]:
        return db.query(PushSubscriptionRecord).all()

    def delete_subscription(self, db: Session, sub_id: int) -> bool:
        rec = db.query(PushSubscriptionRecord).filter(PushSubscriptionRecord.id == sub_id).first()
        if not rec:
            return False
        db.delete(rec)
        db.commit()
        return True

    # --- Versand ---

    def _payload(self, title: str, body: str, url: str, icon: str, priority: str) -> str:
        return json.dumps(
            {
                "title": title,
                "body": body,
                "url": url,
                "icon": icon,
                "priority": priority,
            }
        )

    def send_to_all(
        self,
        db: Session,
        title: str,
        body: str,
        url: str = "/",
        icon: str = "/assets/icons/app-icon-192.png",
        priority: str = "info",
    ) -> Dict[str, int]:
        """Sendet an alle Subscriptions. Gibt Erfolgs-/Fehlerzähler zurück."""
        if not self.is_configured:
            logger.warning("push not configured – skipping send")
            return {"success": 0, "failed": 0, "total": 0}

        subs = self.list_subscriptions(db)
        payload = self._payload(title, body, url, icon, priority)
        claims = {"sub": settings.vapid_email}

        success = failed = 0
        for sub in list(subs):
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": json.loads(sub.keys_json),
                    },
                    data=payload,
                    vapid_private_key=settings.vapid_private_key,
                    vapid_claims=claims,
                    ttl=86400,
                )
                success += 1
            except WebPushException as exc:  # type: ignore[misc]
                failed += 1
                status = getattr(getattr(exc, "response", None), "status_code", None)
                if status in (404, 410):
                    db.delete(sub)
                    db.commit()
                    logger.info("removed stale subscription %s", sub.id)
            except Exception as exc:  # noqa: BLE001
                failed += 1
                logger.warning("push send error: %s", exc)

        return {"success": success, "failed": failed, "total": len(subs)}


notification_service = NotificationService()
