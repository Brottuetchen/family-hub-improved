"""System-Health & Meta-Informationen."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.ai.llm import llm_client
from app.config import settings
from app.services.notifications import notification_service

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    return {
        "status": "online",
        "app": settings.app_name,
        "version": __version__,
        "environment": settings.environment,
        "features": {
            "ai": llm_client.is_configured,
            "push": notification_service.is_configured,
            "weather": settings.weather_enabled,
        },
    }
