"""Hermes AI – Chat (mit Verlauf & Streaming), Werkzeuge, Status."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.agent import run_agent
from app.ai.llm import llm_client
from app.ai.tools import TOOLS, is_allowed
from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.services import chat_history

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str


@router.get("/status")
async def status(current_user: User = Depends(get_current_user)):
    available = [t for t in TOOLS.values() if is_allowed(t.min_role, current_user.role)]
    return {
        "llm_configured": llm_client.is_configured,
        "mode": "llm" if llm_client.is_configured else "rule-based",
        "provider": settings.ai_provider,
        "model": settings.ai_model if llm_client.is_configured else None,
        "role": current_user.role,
        "tool_count": len(available),
    }


@router.get("/tools")
async def tools(current_user: User = Depends(get_current_user)):
    return [
        {"name": t.name, "description": t.description, "min_role": t.min_role}
        for t in TOOLS.values()
        if is_allowed(t.min_role, current_user.role)
    ]


@router.get("/history")
async def history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return chat_history.load_full(db, current_user.id)


@router.delete("/history")
async def clear_history(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    n = chat_history.clear(db, current_user.id)
    return {"cleared": n}


@router.post("/chat")
async def chat(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    hist = chat_history.load_history(db, current_user.id)
    chat_history.save_message(db, current_user.id, "user", data.message)
    result = await run_agent(data.message, db=db, user_id=current_user.id, history=hist)
    chat_history.save_message(db, current_user.id, "assistant", result.get("reply", ""), result.get("actions"))
    return result


@router.post("/stream")
async def stream(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Server-Sent-Events: streamt die Antwort des Assistenten Wort für Wort."""
    hist = chat_history.load_history(db, current_user.id)
    chat_history.save_message(db, current_user.id, "user", data.message)

    async def event_gen():
        try:
            result = await run_agent(data.message, db=db, user_id=current_user.id, history=hist)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})
            return

        reply = result.get("reply", "") or ""
        actions = result.get("actions", [])
        # Antwort tokenweise (wortweise) ausliefern für Streaming-Optik.
        for token in _tokenize(reply):
            yield _sse({"type": "delta", "text": token})
            await asyncio.sleep(0.015)
        chat_history.save_message(db, current_user.id, "assistant", reply, actions)
        yield _sse({"type": "done", "actions": actions, "used_llm": result.get("used_llm", False)})

    return StreamingResponse(event_gen(), media_type="text/event-stream")


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _tokenize(text: str):
    # Erhält Whitespace, damit die Anzeige natürlich fließt.
    import re

    return re.findall(r"\S+\s*", text) or [text]
