"""Laufzeit-Konfiguration: Admin-editierbare Connector-Zugänge (URLs/Tokens).

Overrides landen in der Tabelle ``config_overrides`` und werden auf das globale
``settings``-Objekt angewandt – sofort wirksam, **ohne** `.env`-Bearbeitung oder
Neustart. Secrets werden verschlüsselt gespeichert und nie im Klartext
zurückgegeben.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.logging_config import get_logger
from app.models.config import ConfigOverride

logger = get_logger("service.config_store")

# Editierbare Zugänge je Connector: (settings-Feld, Label, secret?)
CONNECTOR_SETTINGS: List[Dict[str, Any]] = [
    {"name": "caldav", "title": "Kalender (CalDAV/Nextcloud)", "fields": [
        ("caldav_url", "URL", False), ("caldav_username", "Benutzer", False), ("caldav_password", "Passwort", True)]},
    {"name": "vikunja", "title": "Aufgaben (Vikunja)", "fields": [
        ("vikunja_url", "URL", False), ("vikunja_token", "API-Token", True)]},
    {"name": "kitchenowl", "title": "Einkauf (KitchenOwl)", "fields": [
        ("kitchenowl_url", "URL", False), ("kitchenowl_token", "API-Token", True)]},
    {"name": "paperless", "title": "Dokumente (Paperless-ngx)", "fields": [
        ("paperless_url", "URL", False), ("paperless_token", "API-Token", True)]},
    {"name": "homebox", "title": "Inventar (Homebox)", "fields": [
        ("homebox_url", "URL", False), ("homebox_token", "API-Token", True)]},
    {"name": "homeassistant", "title": "Smart Home (Home Assistant)", "fields": [
        ("homeassistant_url", "URL", False), ("homeassistant_token", "Long-Lived Token", True)]},
    {"name": "plex", "title": "Medien (Plex)", "fields": [
        ("plex_url", "URL", False), ("plex_token", "X-Plex-Token", True)]},
    {"name": "audiobookshelf", "title": "Hörbücher (Audiobookshelf)", "fields": [
        ("audiobookshelf_url", "URL", False), ("audiobookshelf_token", "API-Token", True)]},
    {"name": "teddycloud", "title": "Tonies (TeddyCloud)", "fields": [
        ("teddycloud_url", "URL", False)]},
    {"name": "overseerr", "title": "Media-Requests (Overseerr)", "fields": [
        ("overseerr_url", "URL", False), ("overseerr_api_key", "API-Key", True)]},
    {"name": "sonarr", "title": "Serien (Sonarr)", "fields": [
        ("sonarr_url", "URL", False), ("sonarr_api_key", "API-Key", True)]},
    {"name": "radarr", "title": "Filme (Radarr)", "fields": [
        ("radarr_url", "URL", False), ("radarr_api_key", "API-Key", True)]},
    {"name": "hermes_agent", "title": "KI – Nous hermes-agent", "fields": [
        ("hermes_agent_url", "API-URL (…/v1)", False), ("hermes_agent_token", "Token", True), ("hermes_agent_model", "Modell", False)]},
]

FIELD_SECRET: Dict[str, bool] = {
    f[0]: f[2] for g in CONNECTOR_SETTINGS for f in g["fields"]
}
ALL_KEYS = set(FIELD_SECRET)


def apply_overrides(db: Session) -> None:
    """Wendet gespeicherte Overrides auf das ``settings``-Objekt an (Laufzeit)."""
    try:
        rows = db.query(ConfigOverride).all()
    except Exception as exc:  # noqa: BLE001  (z.B. Tabelle fehlt bei sehr altem Stand)
        logger.warning("config_overrides nicht lesbar: %s", exc)
        return
    for row in rows:
        if not hasattr(settings, row.key):
            continue
        value = decrypt(row.value) if row.secret else row.value
        try:
            setattr(settings, row.key, value)
        except Exception as exc:  # noqa: BLE001
            logger.warning("override %s nicht anwendbar: %s", row.key, exc)


def save_overrides(db: Session, values: Dict[str, str]) -> None:
    """Speichert/aktualisiert bekannte Overrides und wendet sie sofort an.

    Secret-Felder mit leerem Wert bleiben unverändert (UI-Maskierung).
    """
    for key, raw in (values or {}).items():
        if key not in ALL_KEYS:
            continue
        secret = FIELD_SECRET[key]
        if secret and not (raw or "").strip():
            continue  # leeres Secret = beibehalten
        value = (raw or "").strip()
        row = db.get(ConfigOverride, key)
        if row is None:
            row = ConfigOverride(key=key)
        row.value = encrypt(value) if secret else value
        row.secret = secret
        db.add(row)
        if hasattr(settings, key):
            setattr(settings, key, value)
    db.commit()
