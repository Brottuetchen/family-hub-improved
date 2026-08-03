"""Finanzen: wiederkehrende Kosten (Daueraufträge, Versicherungen, Abos)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class RecurringExpense(Base):
    __tablename__ = "recurring_expenses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    amount = Column(Float, default=0.0)
    currency = Column(String, default="EUR")
    # weekly | monthly | quarterly | yearly
    interval = Column(String, default="monthly")
    # insurance | subscription | rent | utility | loan | other
    category = Column(String, default="other")
    due_day = Column(Integer, nullable=True)  # Tag im Monat (1-31)
    active = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
