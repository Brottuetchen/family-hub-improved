"""Hermes AI – Chat & Werkzeuge."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.agent import run_agent
from app.ai.llm import llm_client
from app.ai.tools import TOOLS, is_allowed
from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


@router.get("/status")
async def status(current_user: User = Depends(get_current_user)):
    available = [t for t in TOOLS.values() if is_allowed(t.min_role, current_user.role)]
    return {
        "llm_configured": llm_client.is_configured,
        "mode": "llm" if llm_client.is_configured else "rule-based",
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


@router.post("/chat")
async def chat(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return await run_agent(data.message, db=db, user_id=current_user.id, history=data.history)
