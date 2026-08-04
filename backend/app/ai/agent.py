"""Hermes-Chat-Relay.

Das „Assistent"-Chatfenster ist **nur ein dünner Client** zum echten
NousResearch/hermes-agent (Sidecar). hermes ist der Agent: er bringt seine
eigenen Tools/Skills/Memory mit und steuert unsere Familien-Module über den
MCP-Server (``app/mcp/server.py``).

Wir *relayen* hier ausschließlich Chat/Streaming an den Sidecar –
**kein** eigener Tool-Loop und **kein** regelbasiertes Wort-Matching. Ist kein
Sidecar verbunden, gibt es einen klaren Hinweis statt einer Pseudo-Antwort.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.llm import llm_client
from app.core.logging_config import get_logger
from app.models.user import User

logger = get_logger("ai.agent")

# Klarer Hinweis, wenn kein hermes-agent verbunden ist (statt Wort-Matcher).
NOT_CONNECTED = (
    "Der Hermes-Agent ist nicht verbunden. Setze in der .env "
    "AI_PROVIDER=hermes_agent und HERMES_AGENT_URL und starte den Sidecar "
    "(docker compose --profile agent up -d). Details: docs/HERMES_AGENT.md."
)


def build_agentic_messages(
    message: str, history: Optional[List[Dict[str, str]]], user_name: str = "jemand", role: str = "partner"
) -> List[Dict[str, Any]]:
    """Nachrichten für den Relay-Modus (hermes-agent ist der Agent).

    Es werden KEINE Tool-Schemas injiziert – der Sidecar bringt seine eigenen
    Tools/Skills/Memory mit. Ein kurzer System-Hinweis personalisiert nur.
    """
    system = f"Du unterstützt {user_name} (Rolle: {role}) über Hermes Family OS."
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})
    return messages


def not_connected_reply() -> Dict[str, Any]:
    return {"reply": NOT_CONNECTED, "actions": [], "used_llm": False, "connected": False}


async def run_agent(
    message: str,
    db: Session,
    user_id: Optional[int] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Relay der Nachricht an den hermes-agent-Sidecar (kein eigener Agent)."""
    if not (llm_client.is_agentic and llm_client.is_configured):
        return not_connected_reply()

    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    role = (user.role if user else None) or "partner"
    name = (user.full_name or user.username) if user else "jemand"
    try:
        return await _run_relay(message, history or [], name, role)
    except Exception as exc:  # noqa: BLE001
        logger.warning("hermes-agent relay failed: %s", exc)
        return {
            "reply": f"Der Hermes-Agent ist gerade nicht erreichbar ({exc}).",
            "actions": [],
            "used_llm": False,
            "connected": False,
        }


async def _run_relay(message: str, history: List[Dict[str, str]], user_name: str, role: str) -> Dict[str, Any]:
    messages = build_agentic_messages(message, history, user_name, role)
    msg = await llm_client.chat(messages)  # ohne Tools – der Sidecar ist der Agent
    return {"reply": msg.get("content", "") or "", "actions": [], "used_llm": True, "connected": True}
