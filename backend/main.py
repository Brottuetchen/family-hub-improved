"""
Family Hub - FastAPI Backend
Provides API endpoints for stats, push notifications, and service management
NOW WITH SECURE AUTHENTICATION
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from pywebpush import webpush, WebPushException
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import json
import os
import logging
import hashlib
import requests
from pathlib import Path
from datetime import datetime

# Authentication imports
from database import init_db, User
from auth import get_current_user, get_current_admin_user
from auth_router import router as auth_router

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(
    title="Family Hub API",
    description="Backend für Family Hub PWA mit Push Notifications, Stats und Authentication",
    version="3.0.0"
)

# Include authentication router
app.include_router(auth_router)

# Cache Control Middleware
class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Setze Cache-Control für statische Dateien
        if request.url.path.endswith(('.js', '.css')):
            # JavaScript/CSS: Kurze Cache-Zeit, must-revalidate
            response.headers['Cache-Control'] = 'public, max-age=300, must-revalidate'
        elif request.url.path.endswith(('.png', '.jpg', '.jpeg', '.svg', '.ico')):
            # Images: Längere Cache-Zeit
            response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
        elif request.url.path.endswith('.json'):
            # JSON: Keine Cache (immer aktuell)
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'

        return response

# CORS Middleware für lokales Netzwerk
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In Produktion: Nur spezifische Origins erlauben
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache Control Middleware hinzufügen
app.add_middleware(CacheControlMiddleware)

# Recognize X-Forwarded-* headers when running behind a reverse proxy (e.g., on Proxmox)

# === CONFIGURATION ===

# VAPID Keys für Push Notifications
# WICHTIG: Diese Keys müssen generiert werden mit:
# openssl ecparam -genkey -name prime256v1 -out vapid_private.pem
# openssl ec -in vapid_private.pem -pubout -out vapid_public.pem
# Dann mit: python -c "import base64; print(base64.urlsafe_b64encode(open('vapid_public.pem', 'rb').read()))"
VAPID_PRIVATE_KEY = os.getenv(
    "VAPID_PRIVATE_KEY",
    "8MVhjaFj6C0DyMeldIQiJccEtRywAZIxgbvyOVQBtmc"
)
VAPID_PUBLIC_KEY = os.getenv(
    "VAPID_PUBLIC_KEY",
    "BCd4UmkQcwVgZy5kJTm7llHbOBuFwYKTOS3jP3Dn97g_rSUMH_V4WFGVyuJvzwyuzhAOCM3h4K249kilbJK4td0"
)
# Track defaults to detect unconfigured state reliably
_DEFAULT_VAPID_PUBLIC = "BCd4UmkQcwVgZy5kJTm7llHbOBuFwYKTOS3jP3Dn97g_rSUMH_V4WFGVyuJvzwyuzhAOCM3h4K249kilbJK4td0"
VAPID_CLAIMS = {
    "sub": "mailto:trapp.constantin@gmail.com"
}

# Optional: Lade VAPID Keys aus backend/vapid_keys.json, falls nicht per ENV gesetzt
try:
    if (not os.getenv("VAPID_PRIVATE_KEY")) or (not os.getenv("VAPID_PUBLIC_KEY")):
        _vapid_path = Path(__file__).parent / "vapid_keys.json"
        if _vapid_path.exists():
            with open(_vapid_path, "r", encoding="utf-8") as _vf:
                _vk = json.load(_vf)
                VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", _vk.get("private_key", VAPID_PRIVATE_KEY))
                VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", _vk.get("public_key", VAPID_PUBLIC_KEY))
except Exception as _exc:
    logger.warning(f"VAPID keys file load failed: {_exc}")

# Service URLs aus deinem Homelab
PLEX_URL = "http://192.168.188.7:32400"
PLEX_TOKEN = "oe1a9iRoLZktgJEAXFvo"

OVERSEERR_URL = "http://192.168.188.79:5055"
OVERSEERR_API_KEY = "MTc1ODU1NDgxMzY0NGE3MWZjZDY4LWJhMzItNGI5NC1hNDNiLWEyZWViODE4MmE2OQ=="

TEDDYCLOUD_URL = "http://192.168.188.151"

AUDIOBOOKSHELF_URL = "http://192.168.188.84:13378"
AUDIOBOOKSHELF_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJrZXlJZCI6IjI2ODNiZGUzLTlkZWEtNGMxZi04MTEwLWNlNjE0YzQ2N2YyMiIsIm5hbWUiOiJuOG4iLCJ0eXBlIjoiYXBpIiwiaWF0IjoxNzYwMzc4MzU4fQ.oZHbmOOycwyhkLY1G-6NLfdwRE_GKc60xBkU0qGebcU"

NEWSLETTER_DIR = Path('/opt/newsletter-output')
SUBSCRIPTIONS_FILE = Path(os.getenv("PUSH_SUBSCRIPTIONS_FILE", "/opt/newsletter-output/push_subscriptions.json"))

# Fallback fr lokale/dev-Umgebungen (z.B. Windows):
if not SUBSCRIPTIONS_FILE.parent.exists():
    SUBSCRIPTIONS_FILE = Path(__file__).parent / "push_subscriptions.json"

# In-Memory Storage (später: SQLite oder Redis für Persistence)
push_subscriptions: List[Dict] = []


def load_subscriptions_from_file() -> List[Dict]:
    """Load stored push subscriptions from JSON file."""
    if not SUBSCRIPTIONS_FILE.exists():
        logger.info("No persisted push subscriptions found (file missing).")
        return []

    try:
        with open(SUBSCRIPTIONS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            logger.warning("Persisted push subscriptions file malformed (expected list).")
            return []

        valid_subs = []
        for entry in data:
            if isinstance(entry, dict) and "endpoint" in entry and "keys" in entry:
                valid_subs.append(entry)
            else:
                logger.warning("Skipping invalid subscription entry in persisted file.")

        logger.info(f"Loaded {len(valid_subs)} push subscriptions from disk.")
        return valid_subs

    except Exception as exc:
        logger.error(f"Failed to load push subscriptions: {exc}")
        return []


def persist_subscriptions() -> None:
    """Persist current push subscriptions to JSON file."""
    try:
        SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SUBSCRIPTIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(push_subscriptions, f, ensure_ascii=False, indent=2)
        logger.info(f"Persisted {len(push_subscriptions)} push subscriptions.")
    except Exception as exc:
        logger.error(f"Failed to persist push subscriptions: {exc}")


# Load subscriptions at startup
push_subscriptions.extend(load_subscriptions_from_file())

# === PYDANTIC MODELS ===

class PushSubscription(BaseModel):
    endpoint: str
    keys: Dict[str, str]
    # optional metadata fields are accepted but ignored for validation
    # they will be stored as-is if present

class PushNotification(BaseModel):
    title: str
    body: str
    url: Optional[str] = "/"
    icon: Optional[str] = "/assets/icons/app-icon-192.png"

# === ROUTES ===

@app.get("/api/health")
async def health_check():
    """API Health Check"""
    return {
        "status": "online",
        "service": "Family Hub API",
        "version": "2.0.0",
        "endpoints": [
            "/api/vapid-public-key",
            "/api/push/subscribe",
            "/api/push/notify",
            "/api/push/admin/send",
            "/api/services/status",
            "/api/plex/stats",
            "/api/overseerr/stats"
        ]
    }

# === PUSH NOTIFICATIONS ===

@app.get("/api/push/debug")
async def push_debug(current_user: User = Depends(get_current_admin_user)):
    """Debug-Info zur Push-Konfiguration (admin only)."""
    try:
        vapid_source = "env" if (os.getenv("VAPID_PUBLIC_KEY") and os.getenv("VAPID_PRIVATE_KEY")) else (
            "file" if (Path(__file__).parent / "vapid_keys.json").exists() else "default"
        )
        # provider breakdown
        providers = {"apple": 0, "google": 0, "mozilla": 0, "unknown": 0}
        samples = {"apple": None, "google": None, "mozilla": None, "unknown": None}
        for sub in push_subscriptions:
            ep = (sub.get("endpoint") or "").lower()
            key = (
                "apple" if "web.push.apple.com" in ep else
                "google" if "fcm.googleapis.com" in ep or "firebase" in ep else
                "mozilla" if "updates.push.services.mozilla.com" in ep else
                "unknown"
            )
            providers[key] += 1
            if samples[key] is None:
                samples[key] = ep[:72]

        info = {
            "subscriptions_file": str(SUBSCRIPTIONS_FILE),
            "subscriptions_file_exists": SUBSCRIPTIONS_FILE.exists(),
            "subscriptions_count": len(push_subscriptions),
            "vapid_public_key_prefix": (VAPID_PUBLIC_KEY or "")[:24],
            "vapid_source": vapid_source,
            "providers": providers,
            "sample_endpoints": {k: v for k, v in samples.items() if v},
        }
        return info
    except Exception as e:
        logger.error(f"push_debug error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/vapid-public-key")
async def get_vapid_public_key():
    """Gibt VAPID Public Key für Push Subscriptions zurück"""
    # If the current key equals the known default, treat as not configured
    if (VAPID_PUBLIC_KEY or "") == _DEFAULT_VAPID_PUBLIC:
        logger.warning("VAPID keys not configured!")
        raise HTTPException(
            status_code=501,
            detail="Push notifications not configured. Please set VAPID keys."
        )

    return {"publicKey": VAPID_PUBLIC_KEY}

@app.get("/api/push/subscriptions-count")
async def get_subscriptions_count():
    """Returns current subscription count and storage info (no auth)."""
    try:
        return {
            "count": len(push_subscriptions),
            "file": str(SUBSCRIPTIONS_FILE),
            "file_exists": SUBSCRIPTIONS_FILE.exists()
        }
    except Exception as e:
        logger.error(f"subscriptions-count error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/push/subscribe")
async def subscribe_push(subscription: PushSubscription, request: Request):
    """Speichert neue Push Subscription"""
    sub_dict = subscription.dict()
    # add lightweight metadata for debugging (does not affect webpush)
    try:
        ua = request.headers.get("user-agent")
        sub_dict.setdefault("meta", {})
        sub_dict["meta"].update({
            "ua": ua,
            "added_at": datetime.utcnow().isoformat(),
        })
    except Exception:
        pass

    # Prüfe ob bereits existiert
    for existing in push_subscriptions:
        if existing.get("endpoint") == sub_dict["endpoint"]:
            logger.info(f"Subscription already exists: {sub_dict['endpoint'][:50]}...")
            return {"success": True, "message": "Subscription already exists"}

    push_subscriptions.append(sub_dict)
    logger.info(f"New push subscription added. Total: {len(push_subscriptions)}")

    persist_subscriptions()

    return {
        "success": True,
        "message": "Subscription saved",
        "total_subscriptions": len(push_subscriptions)
    }


@app.post("/api/push/admin/test/{subscription_id}")
async def admin_test_push(
    subscription_id: str,
    notification: PushNotification | None = None,
    current_user: User = Depends(get_current_admin_user)
):
    """Send a test push to a single subscription by ID (admin only)."""
    payload = {
        "title": (notification.title if notification else "Family Hub Test"),
        "body": (notification.body if notification else "Testbenachrichtigung"),
        "url": (notification.url if notification else "/"),
        "icon": (notification.icon if notification else "/assets/icons/app-icon-192.png"),
    }

    # find subscription
    target = None
    for sub in push_subscriptions:
        if get_subscription_id(sub) == subscription_id:
            target = sub
            break

    if not target:
        raise HTTPException(status_code=404, detail="Subscription not found")

    try:
        webpush(
            subscription_info=target,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            ttl=86400,
        )
        return {"success": True}
    except WebPushException as e:
        # surface diagnostic info
        detail = {
            "error": str(e),
            "status": getattr(getattr(e, "response", None), "status_code", None),
            "body": None,
        }
        try:
            if e.response is not None:
                detail["body"] = e.response.text
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=detail)

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
    subscriptions_changed = False

    for subscription in push_subscriptions[:]:  # Copy list für safe removal
        try:
            response = webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
                ttl=86400  # 24 hours
            )
            success_count += 1
            logger.info(f"Push sent successfully to {subscription['endpoint'][:50]}...")

        except WebPushException as e:
            logger.error(f"Push failed: {e}")
            failed_count += 1

            # Entferne ungültige Subscriptions (410 Gone, 404 Not Found)
            if e.response and e.response.status_code in [410, 404]:
                push_subscriptions.remove(subscription)
                subscriptions_changed = True
                logger.info(f"Removed invalid subscription: {subscription['endpoint'][:50]}...")
        except Exception as e:
            # Unerwartete Fehler ebenfalls abfangen, damit der Endpoint nicht 500 liefert
            logger.exception(f"Unexpected error sending push: {e}")
            failed_count += 1

    if subscriptions_changed:
        persist_subscriptions()

    return {
        "success": success_count,
        "failed": failed_count,
        "total_subscriptions": len(push_subscriptions)
    }

@app.post("/api/push/admin/send")
async def admin_send_push(
    notification: PushNotification,
    current_user: User = Depends(get_current_admin_user)
):
    """Admin Endpoint: Sende benutzerdefinierte Push-Benachrichtigung (requires admin authentication)"""
    if not push_subscriptions:
        return {"success": 0, "failed": 0, "message": "No subscribers"}

    payload = {
        "title": notification.title,
        "body": notification.body,
        "url": notification.url,
        "icon": notification.icon
    }

    success_count = 0
    failed_count = 0
    subscriptions_changed = False

    for subscription in push_subscriptions[:]:
        try:
            response = webpush(
                subscription_info=subscription,
                data=json.dumps(payload),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=VAPID_CLAIMS,
                ttl=86400
            )
            success_count += 1
            logger.info(f"Admin push sent to {subscription['endpoint'][:50]}...")

        except WebPushException as e:
            logger.error(f"Admin push failed: {e}")
            failed_count += 1

            if e.response and e.response.status_code in [410, 404]:
                push_subscriptions.remove(subscription)
                subscriptions_changed = True
                logger.info(f"Removed invalid subscription: {subscription['endpoint'][:50]}...")
        except Exception as e:
            logger.exception(f"Unexpected error in admin push: {e}")
            failed_count += 1

    if subscriptions_changed:
        persist_subscriptions()

    logger.info(f"Admin notification sent: '{notification.title}' - {success_count} success, {failed_count} failed")

    return {
        "success": success_count,
        "failed": failed_count,
        "total_subscriptions": len(push_subscriptions),
        "message": f"Push notification '{notification.title}' sent successfully"
    }

def get_subscription_id(subscription: Dict) -> str:
    """Creates a unique ID for a subscription based on its endpoint."""
    return hashlib.sha256(subscription.get("endpoint", "").encode("utf-8")).hexdigest()

@app.get("/api/push/subscriptions")
async def get_subscriptions(current_user: User = Depends(get_current_admin_user)):
    """Gibt eine Liste aller Push-Subscriptions zurück (anonymisiert) (requires admin authentication)"""
    return [
        {
            "id": get_subscription_id(sub),
            "endpoint": sub.get("endpoint"),
            # Optional: User-Agent oder andere Infos, falls gespeichert
        }
        for sub in push_subscriptions
    ]

@app.delete("/api/push/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    current_user: User = Depends(get_current_admin_user)
):
    """Löscht eine Push-Subscription anhand ihrer ID (requires admin authentication)"""
    global push_subscriptions
    initial_count = len(push_subscriptions)
    
    original_subscriptions = list(push_subscriptions)
    push_subscriptions = [
        sub for sub in push_subscriptions
        if get_subscription_id(sub) != subscription_id
    ]

    if len(push_subscriptions) < initial_count:
        persist_subscriptions()
        logger.info(f"Subscription {subscription_id} deleted. New count: {len(push_subscriptions)}")
        return {"success": True, "message": "Subscription deleted"}
    else:
        logger.warning(f"Subscription with ID {subscription_id} not found for deletion.")
        raise HTTPException(status_code=404, detail="Subscription not found")



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
        subscriptions_changed = False

        for subscription in push_subscriptions[:]:
            try:
                response = webpush(
                    subscription_info=subscription,
                    data=json.dumps(notification_data),
                    vapid_private_key=VAPID_PRIVATE_KEY,
                    vapid_claims=VAPID_CLAIMS,
                    ttl=86400
                )
                success += 1
            except WebPushException as e:
                logger.error(f"Push failed: {e}")
                failed += 1
                # Entferne ungültige Subscriptions
                if e.response and e.response.status_code in [410, 404]:
                    push_subscriptions.remove(subscription)
                    subscriptions_changed = True
                    logger.info(f"Removed invalid subscription: {subscription['endpoint'][:50]}...")

        if subscriptions_changed:
            persist_subscriptions()

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

# === UNIFIED MEDIA STREAMS ===

@app.get("/api/media/active-streams")
async def get_active_streams():
    """
    Unified endpoint for all active media streams from:
    - Plex (movies, TV shows, music)
    - TeddyCloud (active Tonies playing audiobooks)
    - Audiobookshelf (audiobooks, podcasts)
    """
    all_streams = []

    # 1. Fetch Plex active sessions
    try:
        sessions_url = f"{PLEX_URL}/status/sessions"
        headers = {"Accept": "application/json", "X-Plex-Token": PLEX_TOKEN}
        response = requests.get(sessions_url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        sessions = data.get('MediaContainer', {}).get('Metadata', [])

        for session in sessions:
            # Use grandparent thumb for episodes, regular thumb otherwise
            thumb = session.get("grandparentThumb") if session.get("type") == "episode" else session.get("thumb")

            stream_info = {
                "source": "plex",
                "title": session.get("title", "Unknown"),
                "type": session.get("type", "unknown"),
                "user": session.get("User", {}).get("title", "Unknown User"),
                "progress": session.get("viewOffset", 0),
                "duration": session.get("duration", 0),
                "thumb": f"/api/plex/image{thumb}" if thumb else None,
                "icon": "🎬"
            }

            # For TV episodes: add show name
            if session.get("type") == "episode":
                stream_info["show"] = session.get("grandparentTitle", "")
                stream_info["subtitle"] = f"{stream_info['show']} {session.get('parentIndex', '')}x{session.get('index', '')}"

            all_streams.append(stream_info)

    except Exception as e:
        logger.error(f"Plex sessions error: {e}")

    # 2. Fetch TeddyCloud active Tonies
    try:
        teddycloud_url = f"{TEDDYCLOUD_URL}/api/tonieboxesJson"
        response = requests.get(teddycloud_url, timeout=10)
        response.raise_for_status()

        data = response.json()

        # TeddyCloud returns array of Tonieboxes
        if isinstance(data, list):
            for box in data:
                # Check if there's an active Tonie on this box
                # Structure depends on TeddyCloud response - we'll look for current tag/content
                last_query = box.get("last_query_time")
                if last_query:
                    # Active Toniebox found
                    content = box.get("content", {})
                    tonie_info = {
                        "source": "teddycloud",
                        "title": content.get("title", box.get("name", "Unbekannter Tonie")),
                        "type": "tonie",
                        "user": box.get("boxName", "Toniebox"),
                        "subtitle": content.get("series", "Hörbuch"),
                        "thumb": content.get("picture", None),
                        "icon": "🧸"
                    }
                    all_streams.append(tonie_info)

    except Exception as e:
        logger.error(f"TeddyCloud error: {e}")

    # 3. Fetch Audiobookshelf active sessions
    try:
        abs_sessions_url = f"{AUDIOBOOKSHELF_URL}/api/sessions"
        headers = {"Authorization": f"Bearer {AUDIOBOOKSHELF_TOKEN}"}
        response = requests.get(abs_sessions_url, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        sessions = data.get("sessions", []) if isinstance(data, dict) else data

        for session in sessions:
            # Only show currently open sessions
            if session.get("open", False):
                media_metadata = session.get("mediaMetadata", {})

                abs_info = {
                    "source": "audiobookshelf",
                    "title": media_metadata.get("title", "Unknown Audiobook"),
                    "type": "audiobook",
                    "user": session.get("displayTitle", "Unknown User"),
                    "subtitle": media_metadata.get("authorName", ""),
                    "progress": session.get("currentTime", 0),
                    "duration": session.get("duration", 0),
                    "thumb": session.get("coverPath", None),
                    "icon": "📚"
                }
                all_streams.append(abs_info)

    except Exception as e:
        logger.error(f"Audiobookshelf error: {e}")

    return {
        "active_streams": len(all_streams),
        "streams": all_streams,
        "timestamp": datetime.now().isoformat()
    }

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
                "duration": session.get("duration", 0),
                "thumb": session.get("thumb"),
                "art": session.get("art"),
                "grandparentThumb": session.get("grandparentThumb")
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

        recent = []
        for item in recent_items:
            thumb_path = item.get("thumb")
            thumb_url = None
            if thumb_path:
                # Return relative path - frontend will proxy through backend
                thumb_url = f"/api/plex/image{thumb_path}"

            recent.append({
                "title": item.get("title", "Unknown"),
                "type": item.get("type", "unknown"),
                "year": item.get("year"),
                "added": item.get("addedAt"),
                "summary": item.get("summary", ""),
                "ratingKey": item.get("ratingKey"),
                "thumb_url": thumb_url
            })

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

# === PLEX IMAGE PROXY ===

@app.get("/api/plex/image/{path:path}")
async def proxy_plex_image(path: str):
    """Proxy Plex images through HTTPS backend to avoid mixed content"""
    try:
        image_url = f"{PLEX_URL}/{path}?X-Plex-Token={PLEX_TOKEN}"
        response = requests.get(image_url, timeout=10, stream=True)
        response.raise_for_status()

        return Response(
            content=response.content,
            media_type=response.headers.get('Content-Type', 'image/jpeg'),
            headers={
                'Cache-Control': 'public, max-age=86400',
                'Access-Control-Allow-Origin': '*'
            }
        )
    except Exception as e:
        logger.error(f"Plex image proxy error: {e}")
        raise HTTPException(status_code=404, detail="Image not found")

# === PLEX METADATA (for frontend enrichment) ===

@app.get("/api/plex/metadata/{rating_key}")
async def get_plex_metadata(rating_key: str):
    """Fetch Plex metadata for a given rating key and return essential fields.

    Keeps response minimal for frontend use (title, type, thumbs).
    """
    try:
        url = f"{PLEX_URL}/library/metadata/{rating_key}"
        headers = {
            "Accept": "application/json",
            "X-Plex-Token": PLEX_TOKEN,
        }
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()

        # Try to parse JSON, otherwise return minimal fallback
        try:
            data = response.json()
            item = (
                data.get("MediaContainer", {})
                .get("Metadata", [{}])[0]
            )
            thumb_path = item.get("thumb")
            result = {
                "title": item.get("title"),
                "type": item.get("type"),
                "ratingKey": item.get("ratingKey", rating_key),
                "thumb": thumb_path,
                "thumb_url": f"/api/plex/image{thumb_path}" if thumb_path else None,
                "art": item.get("art"),
                "grandparentThumb": item.get("grandparentThumb"),
            }
            return result
        except ValueError:
            # Non-JSON (e.g., XML) – return minimal fields only
            return {"ratingKey": rating_key}

    except requests.exceptions.RequestException as e:
        logger.error(f"Plex metadata error: {e}")
        raise HTTPException(status_code=502, detail="Could not fetch Plex metadata")
    except Exception as e:
        logger.error(f"Unexpected plex metadata error: {e}")
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
if NEWSLETTER_DIR.exists():
    app.mount('/newsletters', StaticFiles(directory=str(NEWSLETTER_DIR)), name='newsletters')
    logger.info(f'Serving newsletters from: {NEWSLETTER_DIR}')
else:
    logger.warning(f'Newsletter output directory not found: {NEWSLETTER_DIR}')

if static_path.exists():
    app.mount('/', StaticFiles(directory=str(static_path), html=True), name='static')
    logger.info(f'Serving static files from: {static_path}')
else:
    logger.warning(f'Static files directory not found: {static_path}')

# === STARTUP / SHUTDOWN ===

@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("Family Hub API started with AUTHENTICATION")

    # Initialize database
    init_db()
    logger.info("Database initialized")

    logger.info(f"VAPID configured: {VAPID_PUBLIC_KEY != 'BMu4f7EOE-CxK2xrMMAa587Fmu_keSyYClMEEq4QjWE2UXagXIEJl0Q-aHuA_lDC8KKabeENonCOrSkq6yoWiLg'}")
    logger.info(f"Push subscriptions: {len(push_subscriptions)}")
    logger.info("=" * 50)
    logger.info("IMPORTANT: Create admin user with: python create_admin.py")
    logger.info("=" * 50)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Family Hub API shutting down...")
    # TODO: Speichere push_subscriptions in Datei/DB

# === MAIN ===

if __name__ == "__main__":
    import uvicorn

    # Production Server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False  # No auto-reload for production
    )
