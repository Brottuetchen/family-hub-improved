"""Hermes AI – Chat (mit Verlauf & Streaming), Werkzeuge, Status."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
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
    if llm_client.is_agentic:
        mode = "hermes-agent"
    elif llm_client.is_configured:
        mode = "llm"
    else:
        mode = "rule-based"
    return {
        "llm_configured": llm_client.is_configured,
        "mode": mode,
        "provider": settings.ai_provider,
        "agentic": llm_client.is_agentic,
        "model": llm_client.model if llm_client.is_configured else None,
        "dashboard": bool(settings.hermes_agent_dashboard_url),
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

    user_name = current_user.full_name or current_user.username

    async def _chunked(reply: str, actions):
        for token in _tokenize(reply):
            yield _sse({"type": "delta", "text": token})
            await asyncio.sleep(0.015)
        chat_history.save_message(db, current_user.id, "assistant", reply, actions)
        yield _sse({"type": "done", "actions": actions})

    async def event_gen():
        # 1) hermes-agent (Relay): echtes Token-Streaming vom Sidecar
        if llm_client.is_agentic:
            from app.ai.agent import build_agentic_messages

            messages = build_agentic_messages(data.message, hist, user_name, current_user.role)
            full = ""
            try:
                async for delta in llm_client.stream_chat(messages):
                    full += delta
                    yield _sse({"type": "delta", "text": delta})
                chat_history.save_message(db, current_user.id, "assistant", full, [])
                yield _sse({"type": "done", "actions": []})
                return
            except Exception as exc:  # noqa: BLE001
                # Sidecar nicht erreichbar -> regelbasierter Fallback
                result = await run_agent(data.message, db=db, user_id=current_user.id, history=hist)
                async for ev in _chunked(result.get("reply", "") or "", result.get("actions", [])):
                    yield ev
                return

        # 2) Direktes Modell / Regel-Fallback: Antwort berechnen und gechunkt streamen
        try:
            result = await run_agent(data.message, db=db, user_id=current_user.id, history=hist)
        except Exception as exc:  # noqa: BLE001
            yield _sse({"type": "error", "message": str(exc)})
            return
        async for ev in _chunked(result.get("reply", "") or "", result.get("actions", [])):
            yield ev

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.post("/voice")
async def voice(audio: UploadFile = File(...), current_user: User = Depends(get_current_user)):
    """Transkribiert eine Sprachnachricht (Audio) zu Text.

    Der Client schickt das transkribierte Ergebnis anschließend wie eine normale
    Chat-Nachricht an ``/api/ai/stream`` (Voice-Message-Flow).
    """
    if not llm_client.is_configured:
        raise HTTPException(status_code=501, detail="Kein KI-Backend konfiguriert (Transkription nicht möglich).")
    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Leere Audiodatei.")
    try:
        text = await llm_client.transcribe(content, audio.filename or "audio.webm", audio.content_type or "audio/webm")
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Transkription fehlgeschlagen: {exc}")
    return {"text": text}


def _sse(payload: Dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _tokenize(text: str):
    # Erhält Whitespace, damit die Anzeige natürlich fließt.
    import re

    return re.findall(r"\S+\s*", text) or [text]
