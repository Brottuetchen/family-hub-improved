"""Hermes Family OS – FastAPI Application.

Assembliert alle Router, Middleware und das statische Frontend (PWA).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.core.database import init_db
from app.core.logging_config import get_logger, setup_logging
from app.services.scheduler import run_scheduler
from app.routers import (
    agent_proxy,
    ai,
    auth,
    calendar,
    connectors,
    dashboard,
    documents,
    family,
    finance,
    health,
    inventory,
    maintenance,
    meals,
    media,
    notifications,
    packages,
    recipes,
    reminders,
    search,
    shopping,
    smarthome,
    tasks,
)

setup_logging()
logger = get_logger("hermes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("%s v%s starting (%s)", settings.app_name, __version__, settings.environment)
    init_db()
    logger.info("Database initialized: %s", settings.database_url)
    logger.info("AI: %s | Push: %s", settings.ai_provider, bool(settings.vapid_public_key))
    if settings.secret_key == "CHANGE_ME_dev_only_secret_key":
        logger.warning("SECRET_KEY is default – set a strong SECRET_KEY in production!")
    logger.info("Tip: create the first admin with 'python -m scripts.create_admin'")
    logger.info("=" * 60)

    # Hintergrund-Scheduler (fällige Erinnerungen -> Push)
    scheduler_task = asyncio.create_task(run_scheduler())
    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title=f"{settings.app_name} API",
    description=(
        "Hermes Family OS – die intelligente Schicht über euren self-hosted "
        "Diensten. Termine, Aufgaben, Einkäufe, Dokumente, Smart Home und KI in "
        "einer Oberfläche."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API-Router
for module in (
    health,
    auth,
    dashboard,
    calendar,
    tasks,
    shopping,
    documents,
    inventory,
    smarthome,
    packages,
    reminders,
    finance,
    family,
    recipes,
    meals,
    maintenance,
    search,
    ai,
    notifications,
    connectors,
    media,
    agent_proxy,
):
    app.include_router(module.router)


# --- Statisches Frontend (PWA) ---
# WICHTIG: Muss NACH allen API-Routern gemountet werden.
_public_dir = Path(__file__).resolve().parent.parent.parent / "public"
if _public_dir.exists():
    app.mount("/", StaticFiles(directory=str(_public_dir), html=True), name="frontend")
    logger.info("Serving frontend from %s", _public_dir)
else:
    logger.warning("Frontend directory not found: %s", _public_dir)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)
