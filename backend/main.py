"""
Family Hub - FastAPI Backend
Provides API endpoints for stats, push notifications, and service management
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pywebpush import webpush, WebPushException
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import logging
import requests
from pathlib import Path
from datetime import datetime

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Family Hub API",
    description="Backend für Family Hub PWA mit Push Notifications und Stats",
    version="2.0.0"
)

# CORS Middleware für lokales Netzwerk
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In Produktion: Nur spezifische Origins erlauben
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === CONFIGURATION ===

# VAPID Keys für Push Notifications
# WICHTIG: Diese Keys müssen generiert werden mit:
# openssl ecparam -genkey -name prime256v1 -out vapid_private.pem
# openssl ec -in vapid_private.pem -pubout -out vapid_public.pem
# Dann mit: python -c "import base64; print(base64.urlsafe_b64encode(open('vapid_public.pem', 'rb').read()))"
VAPID_PRIVATE_KEY = os.getenv(
    "VAPID_PRIVATE_KEY",
    "jqSDEM10LnAAJ1vaMPNQPA4yiGAtz4CNCPRbhY0aS74"  # Wird bei Deployment ersetzt
)
VAPID_PUBLIC_KEY = os.getenv(
    "VAPID_PUBLIC_KEY",
    "BMu4f7EOE-CxK2xrMMAa587Fmu_keSyYClMEEq4QjWE2UXagXIEJl0Q-aHuA_lDC8KKabeENonCOrSkq6yoWiLg"   # Wird bei Deployment ersetzt
)
VAPID_CLAIMS = {
    "sub": "mailto:trapp.constantin@gmail.com"
}

# Service URLs aus deinem Homelab
PLEX_URL = "http://192.168.188.7:32400"
PLEX_TOKEN = "oe1a9iRoLZktgJEAXFvo"

OVERSEERR_URL = "http://192.168.188.79:5055"
OVERSEERR_API_KEY = "MTc1ODU1NDgxMzY0NGE3MWZjZDY4LWJhMzItNGI5NC1hNDNiLWEyZWViODE4MmE2OQ=="

# In-Memory Storage (später: SQLite oder Redis für Persistence)
push_subscriptions: List[Dict] = []

# === PYDANTIC MODELS ===

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]

class PushNotification(BaseModel):
    title: str
    body: str
    url: Optional[str] = "/"
    icon: Optional[str] = "/assets/icons/app-icon-192.png"

# === ROUTES ===

@app.get("/")
async def root():
    """API Health Check"""
    return {
        "status": "online",
        "service": "Family Hub API",
        "version": "2.0.0",
        "endpoints": [
            "/api/vapid-public-key",
            "/api/push/subscribe",
            "/api/push/notify",
            "/api/services/status",
            "/api/plex/stats",
            "/api/overseerr/stats"
        ]
    }

# === PUSH NOTIFICATIONS ===

@app.get("/api/vapid-public-key")
async def get_vapid_public_key():
    """Gibt VAPID Public Key für Push Subscriptions zurück"""
    if VAPID_PUBLIC_KEY == "BMu4f7EOE-CxK2xrMMAa587Fmu_keSyYClMEEq4QjWE2UXagXIEJl0Q-aHuA_lDC8KKabeENonCOrSkq6yoWiLg":
        logger.warning("VAPID keys not configured!")
        raise HTTPException(
            status_code=501,
            detail="Push notifications not configured. Please set VAPID keys."
        )

    return {"publicKey": VAPID_PUBLIC_KEY}

@app.post("/api/push/subscribe")
async def subscribe_push(subscription: PushSubscription):
    """Speichert neue Push Subscription"""
    sub_dict = subscription.dict()

    # Prüfe ob bereits existiert
    for existing in push_subscriptions:
        if existing.get("endpoint") == sub_dict["endpoint"]:
            logger.info(f"Subscription already exists: {sub_dict['endpoint'][:50]}...")
            return {"success": True, "message": "Subscription already exists"}

    push_subscriptions.append(sub_dict)
    logger.info(f"New push subscription added. Total: {len(push_subscriptions)}")

    # TODO: Speichere in Datenbank

    return {
        "success": True,
        "message": "Subscription saved",
        "total_subscriptions": len(push_subscriptions)
    }

@app.post("/api/push/notify")
async def send_push_notification(data: Dict):
    """Sendet Push Notification an alle Subscribers"""
    if not push_subscriptions:
        return {"success": 0, "failed": 0, "message": "No subscribers"}

    title = data.get("title", "Family Hub")
    body = data.get("body", "Neue Updates verfügbar")
    url = data.get("url", "/")
    icon = data.get("icon", "/assets/icons/app-icon-192.png")

    payload = {
        "title": title,
        "body": body,
        "url": url,
        "icon": icon
    }

    success_count = 0
    failed_count = 0

    for subscription in push_subscriptions[:]:  # Copy list für safe removal
        try:
            webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS
            )
            success_count += 1
            logger.info(f"Push sent successfully to {subscription['endpoint'][:50]}...")

        except WebPushException as e:
            logger.error(f"Push failed: {e}")
            failed_count += 1

            # Entferne ungültige Subscriptions (410 Gone, 404 Not Found)
            if e.response and e.response.status_code in [410, 404]:
                push_subscriptions.remove(subscription)
                logger.info(f"Removed invalid subscription")

    return {
        "success": success_count,
        "failed": failed_count,
        "total_subscriptions": len(push_subscriptions)
    }

@app.post("/api/newsletter/reload")
async def reload_newsletter():
    """
    Triggered Newsletter-Reload im Frontend
    Sendet Push Notification an alle Subscriber
    """
    try:
        # Newsletter Index neu laden
        newsletter_path = Path("../public/newsletters/index.json")

        if not newsletter_path.exists():
            return {"success": False, "error": "Newsletter index not found"}

        with open(newsletter_path, 'r', encoding='utf-8') as f:
            newsletters = json.load(f)

        if not newsletters:
            return {"success": False, "error": "No newsletters available"}

        # Neuester Newsletter
        latest = newsletters[0]

        # Push Notification an alle Subscriber
        title = "📰 Neuer Newsletter!"
        body = f"{latest['title']} ist verfügbar!"

        notification_data = {
            "title": title,
            "body": body,
            "url": "/index.html#newsletter",
            "icon": "/assets/icons/app-icon-192.png"
        }

        # Push senden
        failed = 0
        success = 0

        for subscription in push_subscriptions[:]:
            try:
                webpush(
                    subscription_info=subscription,
                    data=json.dumps(notification_data),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS
                )
                success += 1
            except WebPushException as e:
                logger.error(f"Push failed: {e}")
                failed += 1
                # Entferne ungültige Subscriptions
                if e.response and e.response.status_code in [410, 404]:
                    push_subscriptions.remove(subscription)

        return {
            "success": True,
            "newsletter": latest,
            "push_sent": success,
            "push_failed": failed
        }

    except Exception as e:
        logger.error(f"Newsletter reload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# === SERVICE STATUS ===

@app.get("/api/services/status")
async def get_services_status():
    """Prüft Status aller Homelab Services"""
    services = [
        {"name": "Plex", "url": PLEX_URL, "category": "media"},
        {"name": "Overseerr", "url": OVERSEERR_URL, "category": "media"},
        {"name": "Trilium", "url": "http://192.168.188.62:8080", "category": "productivity"},
        {"name": "Immich", "url": "http://192.168.188.94:2283", "category": "productivity"},
        {"name": "Nextcloud", "url": "http://192.168.188.139:443", "category": "productivity"},
        {"name": "SABnzbd", "url": "http://192.168.188.90:8080", "category": "automation"},
        {"name": "Sonarr", "url": "http://192.168.188.71:8989", "category": "automation"},
        {"name": "Radarr", "url": "http://192.168.188.73:7878", "category": "automation"},
    ]

    status_list = []

    for service in services:
        try:
            response = requests.get(service["url"], timeout=3, verify=False)
            status = "online" if response.status_code < 500 else "error"
        except requests.exceptions.Timeout:
            status = "timeout"
        except requests.exceptions.ConnectionError:
            status = "offline"
        except Exception as e:
            logger.error(f"Error checking {service['name']}: {e}")
            status = "error"

        status_list.append({
            "name": service["name"],
            "status": status,
            "category": service["category"]
        })

    return status_list

# === PLEX STATS ===

@app.get("/api/plex/stats")
async def get_plex_stats():
    """Hole aktuelle Plex Statistiken"""
    try:
        # Current Sessions (aktive Streams)
        sessions_url = f"{PLEX_URL}/status/sessions"
        headers = {
            "Accept": "application/json",
            "X-Plex-Token": PLEX_TOKEN
        }

        response = requests.get(sessions_url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        sessions = data.get('MediaContainer', {}).get('Metadata', [])

        # Extrahiere relevante Infos
        streams = []
        for session in sessions:
            stream_info = {
                "title": session.get("title", "Unknown"),
                "type": session.get("type", "unknown"),  # movie, episode, track
                "user": session.get("User", {}).get("title", "Unknown User"),
                "progress": session.get("viewOffset", 0),
                "duration": session.get("duration", 0)
            }

            # Für TV-Episoden: Show-Name hinzufügen
            if session.get("type") == "episode":
                stream_info["show"] = session.get("grandparentTitle", "")
                stream_info["title"] = f"{stream_info['show']} {session.get('parentIndex', '')}x{session.get('index', '')} - {stream_info['title']}"

            streams.append(stream_info)

        # Recently Added (optional)
        recent_url = f"{PLEX_URL}/library/recentlyAdded"
        recent_response = requests.get(recent_url, headers=headers, timeout=5)
        recent_data = recent_response.json()
        recent_items = recent_data.get('MediaContainer', {}).get('Metadata', [])[:5]

        recent = [
            {
                "title": item.get("title", "Unknown"),
                "type": item.get("type", "unknown"),
                "year": item.get("year"),
                "added": item.get("addedAt")
            }
            for item in recent_items
        ]

        return {
            "active_streams": len(streams),
            "streams": streams,
            "recently_added": recent,
            "timestamp": datetime.now().isoformat()
        }

    except requests.exceptions.Timeout:
        logger.error("Plex API timeout")
        raise HTTPException(status_code=504, detail="Plex server timeout")

    except requests.exceptions.RequestException as e:
        logger.error(f"Plex API error: {e}")
        raise HTTPException(status_code=502, detail="Could not connect to Plex")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# === OVERSEERR STATS ===

@app.get("/api/overseerr/stats")
async def get_overseerr_stats():
    """Hole Overseerr Request-Statistiken"""
    try:
        # Pending Requests
        requests_url = f"{OVERSEERR_URL}/api/v1/request"
        headers = {
            "X-Api-Key": OVERSEERR_API_KEY,
            "Accept": "application/json"
        }
        params = {
            "take": 20,
            "skip": 0,
            "filter": "pending"
        }

        response = requests.get(requests_url, headers=headers, params=params, timeout=5)
        response.raise_for_status()

        data = response.json()
        pending_requests = data.get("results", [])

        recent_requests = []
        for req in pending_requests[:10]:
            media = req.get("media", {})
            request_info = {
                "id": req.get("id"),
                "type": media.get("mediaType", "unknown"),
                "title": media.get("title") or media.get("name", "Unknown"),
                "status": req.get("status", 0),
                "requested_by": req.get("requestedBy", {}).get("displayName", "Unknown"),
                "created_at": req.get("createdAt")
            }
            recent_requests.append(request_info)

        return {
            "pending_requests": len(pending_requests),
            "recent_requests": recent_requests,
            "timestamp": datetime.now().isoformat()
        }

    except requests.exceptions.RequestException as e:
        logger.error(f"Overseerr API error: {e}")
        raise HTTPException(status_code=502, detail="Could not connect to Overseerr")

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# === BACKGROUND TASKS ===

async def check_new_content():
    """Background Task: Prüfe auf neue Plex Inhalte und sende Push"""
    # TODO: Implementiere regelmäßige Checks
    pass

# === STATIC FILES (Frontend) ===

# Mount static files (Frontend)
# WICHTIG: Dies muss am Ende stehen!
static_path = Path(__file__).parent.parent / "public"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")
    logger.info(f"Serving static files from: {static_path}")
else:
    logger.warning(f"Static files directory not found: {static_path}")

# === STARTUP / SHUTDOWN ===

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("Family Hub API started")
    logger.info(f"VAPID configured: {VAPID_PUBLIC_KEY != 'BMu4f7EOE-CxK2xrMMAa587Fmu_keSyYClMEEq4QjWE2UXagXIEJl0Q-aHuA_lDC8KKabeENonCOrSkq6yoWiLg'}")
    logger.info(f"Push subscriptions: {len(push_subscriptions)}")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Family Hub API shutting down...")
    # TODO: Speichere push_subscriptions in Datei/DB

# === MAIN ===

if __name__ == "__main__":
    import uvicorn

    # Development Server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=True  # Auto-reload bei Code-Änderungen
    )
