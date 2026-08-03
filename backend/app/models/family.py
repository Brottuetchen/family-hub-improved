"""Familienmitglied-Profile."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.core.database import Base


class FamilyMember(Base):
    """Ein Mitglied der Familie.

    Jedes Mitglied hat ein Profil, eine Farbe (für Kalender-Farbcodierung),
    optional einen Avatar und ein Geburtsdatum (für Geburtstags-Erinnerungen).
    """

    __tablename__ = "family_members"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    # Farbcode für Kalender/Aufgaben (Hex, z.B. #4f46e5)
    color = Column(String, default="#4f46e5")
    avatar = Column(String, nullable=True)  # URL oder Emoji
    role = Column(String, default="partner")  # admin | partner | child | guest
    birthday = Column(String, nullable=True)  # ISO Datum YYYY-MM-DD
    user_id = Column(Integer, nullable=True)  # Verknüpfung zu einem Login-Account

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
