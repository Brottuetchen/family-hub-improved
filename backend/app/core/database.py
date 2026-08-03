"""Datenbank-Setup (SQLAlchemy).

Standard ist SQLite (Zero-Config). Für Produktion kann via ``DATABASE_URL``
auf PostgreSQL umgestellt werden (siehe docker-compose.yml).
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

DATABASE_URL = settings.database_url

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db() -> None:
    """Erstellt alle Tabellen (idempotent)."""
    # Import der Modelle stellt sicher, dass sie bei Base registriert sind.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI-Dependency für eine DB-Session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
