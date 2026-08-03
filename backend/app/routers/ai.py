"""Hermes AI – Chat & Werkzeuge."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.agent import run_agent
from app.ai.llm import llm_client
from app.ai.tools import TOOLS
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None


@router.get("/status")
async def status(current_user: User = Depends(get_current_user)):
    return {
        "llm_configured": llm_client.is_configured,
        "mode": "llm" if llm_client.is_configured else "rule-based",
        "tool_count": len(TOOLS),
    }


@router.get("/tools")
async def tools(current_user: User = Depends(get_current_user)):
    return [
        {"name": t.name, "description": t.description}
        for t in TOOLS.values()
    ]


@router.post("/chat")
async def chat(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> Dict[str, Any]:
    return await run_agent(data.message, db=db, user_id=current_user.id, history=data.history)
