"""Persistente Push-Subscriptions (Web Push / VAPID)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class PushSubscriptionRecord(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    endpoint = Column(String, unique=True, index=True, nullable=False)
    # keys als JSON-String {"auth": ..., "p256dh": ...}
    keys_json = Column(Text, nullable=False)
    user_agent = Column(String, nullable=True)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
