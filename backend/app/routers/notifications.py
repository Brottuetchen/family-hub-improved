"""Push-Notification-Endpunkte (Web Push / VAPID)."""

from __future__ import annotations

import asyncio
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_admin_user, get_current_user
from app.models.user import User
from app.services.notifications import notification_service

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: Dict[str, str]


class SendRequest(BaseModel):
    title: str
    body: str
    url: str = "/"
    icon: str = "/assets/icons/app-icon-192.png"
    priority: str = "info"


@router.get("/vapid-public-key")
async def vapid_public_key():
    if not notification_service.is_configured:
        raise HTTPException(status_code=501, detail="Push notifications not configured (set VAPID keys)")
    return {"publicKey": notification_service.public_key}


@router.post("/subscribe")
async def subscribe(data: SubscribeRequest, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    notification_service.add_subscription(
        db,
        endpoint=data.endpoint,
        keys=data.keys,
        user_agent=request.headers.get("user-agent"),
        user_id=current_user.id,
    )
    return {"success": True}


@router.get("/subscriptions")
async def list_subscriptions(db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    subs = notification_service.list_subscriptions(db)
    return [{"id": s.id, "endpoint": s.endpoint, "user_id": s.user_id} for s in subs]


@router.delete("/subscriptions/{sub_id}")
async def delete_subscription(sub_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    if not notification_service.delete_subscription(db, sub_id):
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"success": True}


@router.post("/send")
async def send(data: SendRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_admin_user)):
    result = await asyncio.to_thread(
        notification_service.send_to_all, db, data.title, data.body, data.url, data.icon, data.priority
    )
    return result
