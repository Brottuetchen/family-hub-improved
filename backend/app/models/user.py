"""Benutzer- und Authentifizierungs-Modelle."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.core.database import Base

# Rollen im System. Jede Rolle besitzt eigene Rechte (siehe app/core/security.py).
ROLE_ADMIN = "admin"
ROLE_PARTNER = "partner"
ROLE_CHILD = "child"
ROLE_GUEST = "guest"
VALID_ROLES = {ROLE_ADMIN, ROLE_PARTNER, ROLE_CHILD, ROLE_GUEST}


class User(Base):
    """Benutzerkonto mit Rollenmodell."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)

    # Rolle: admin | partner | child | guest
    role = Column(String, default=ROLE_PARTNER, nullable=False)
    is_active = Column(Boolean, default=True)
    # is_admin bleibt für Abwärtskompatibilität erhalten und wird aus role abgeleitet.
    is_admin = Column(Boolean, default=False)

    # Optionale Verknüpfung zu einem Familienmitglied-Profil (Avatar, Farbe, ...)
    family_member_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)


class RefreshToken(Base):
    """Refresh-Token für Session-Management."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked = Column(Boolean, default=False)
    user_agent = Column(String, nullable=True)
    ip_address = Column(String, nullable=True)


class LoginAttempt(Base):
    """Protokoll fehlgeschlagener/erfolgreicher Logins (Rate-Limiting)."""

    __tablename__ = "login_attempts"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    ip_address = Column(String, index=True, nullable=False)
    success = Column(Boolean, default=False)
    attempted_at = Column(DateTime, default=datetime.utcnow, index=True)
