"""Authentifizierter Reverse-Proxy für das hermes-agent-Dashboard.

Bettet das komplette hermes-agent-Web-UI unter ``/agent/*`` – hinter unserem
Login – in Hermes Family OS ein (Nav-Punkt „Hermes Agent"). So sind alle
Funktionen (Skills, Memory, Subagents, Tools/Cron/Messaging) in unserer App
verfügbar, ohne sie nachzubauen.

Hinweise / bewusste Grenzen (v1):
  * Auth über unseren access_token (Bearer ODER Cookie – iframe-Navigationen
    senden nur Cookies).
  * Antwort-Header werden bereinigt, damit die Einbettung erlaubt ist
    (X-Frame-Options entfernt; same-origin, da unter unserer Domain).
  * WebSocket-Endpunkte (z.B. Dashboard-PTY) werden hier NICHT geproxied –
    das ist ein bekannter Folgeschritt.
"""

from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.security import verify_token
from app.models.user import User

logger = get_logger("agent.proxy")
router = APIRouter(prefix="/agent", tags=["hermes-agent"])

# Header, die wir NICHT durchreichen.
_DROP_REQUEST = {"host", "content-length", "connection"}
_DROP_RESPONSE = {
    "content-encoding", "content-length", "transfer-encoding", "connection",
    "x-frame-options", "content-security-policy",
}


async def require_dashboard_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Auth via Bearer-Header ODER access_token-Cookie (für iframe-Navigation)."""
    token: Optional[str] = None
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
    if not token:
        token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.query(User).filter(User.username == payload.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Unknown or inactive user")
    return user


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request, user: User = Depends(require_dashboard_user)):
    if not settings.hermes_agent_dashboard_url:
        raise HTTPException(status_code=503, detail="hermes-agent dashboard not configured")

    target = f"{settings.hermes_agent_dashboard_url.rstrip('/')}/{path}"
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_REQUEST}
    body = await request.body()

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=settings.verify_tls, follow_redirects=False) as client:
            upstream = await client.request(
                request.method, target, params=dict(request.query_params), content=body, headers=fwd_headers
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("dashboard proxy error: %s", exc)
        raise HTTPException(status_code=502, detail=f"hermes-agent unreachable: {exc}")

    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _DROP_RESPONSE}
    # Einbettung im selben Origin erlauben.
    resp_headers["Content-Security-Policy"] = "frame-ancestors 'self'"
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)
