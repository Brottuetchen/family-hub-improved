"""Wartungspläne (Auto, Haus, Garten, Geräte)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from app.core.database import Base


class MaintenanceTask(Base):
    __tablename__ = "maintenance_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    # car | home | garden | appliance | other
    category = Column(String, default="other")
    interval_days = Column(Integer, nullable=True)  # Wiederholung in Tagen
    last_done = Column(Date, nullable=True)
    next_due = Column(Date, nullable=True, index=True)
    family_member_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
