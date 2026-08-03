"""Verwaltung des Chat-Verlaufs pro Nutzer."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.chat import ChatMessage

MAX_CONTEXT_MESSAGES = 12


def load_history(db: Session, user_id: int, limit: int = MAX_CONTEXT_MESSAGES) -> List[Dict[str, str]]:
    """Letzte Nachrichten als [{role, content}] (chronologisch) für den LLM-Kontext."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.id.desc())
        .limit(limit)
        .all()
    )
    return [{"role": r.role, "content": r.content} for r in reversed(rows)]


def load_full(db: Session, user_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    """Vollständiger Verlauf für die UI (inkl. Aktionen)."""
    rows = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.id.asc())
        .limit(limit)
        .all()
    )
    out = []
    for r in rows:
        item: Dict[str, Any] = {"id": r.id, "role": r.role, "content": r.content}
        if r.actions_json:
            try:
                item["actions"] = json.loads(r.actions_json)
            except ValueError:
                item["actions"] = []
        out.append(item)
    return out


def save_message(
    db: Session, user_id: int, role: str, content: str, actions: Optional[List[str]] = None
) -> ChatMessage:
    msg = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        actions_json=json.dumps(actions) if actions else None,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def clear(db: Session, user_id: int) -> int:
    n = db.query(ChatMessage).filter(ChatMessage.user_id == user_id).delete()
    db.commit()
    return n
