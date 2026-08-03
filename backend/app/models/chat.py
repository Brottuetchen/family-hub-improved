"""Chat-Verlauf (pro Nutzer) für den Hermes-Assistenten."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    # role: user | assistant
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    # ausgeführte Werkzeuge (JSON-Array) – nur bei Assistant-Nachrichten
    actions_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
