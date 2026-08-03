"""Zentrale Konfiguration für Hermes Family OS.

Alle Einstellungen werden aus Umgebungsvariablen (oder einer ``.env`` Datei)
gelesen. Es werden bewusst KEINE Secrets im Code hinterlegt. Jeder Connector
ist optional: Fehlt die Konfiguration, läuft Hermes im "Demo-Modus" und der
betreffende Baustein liefert leere/Beispiel-Daten statt einen Fehler zu werfen.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Applikationsweite Einstellungen (env-driven)."""

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App / Server ---
    app_name: str = "Hermes Family OS"
    environment: str = Field(default="development")  # development | production
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"
    timezone: str = "Europe/Berlin"

    # TLS-Verifikation für ausgehende Connector-Requests. Im Homelab mit
    # selbst-signierten Zertifikaten ggf. auf false setzen.
    verify_tls: bool = True
    # Standard-Timeout (Sekunden) für Connector-HTTP-Requests.
    connector_timeout: float = 6.0

    # --- Security / Auth ---
    secret_key: str = Field(default="CHANGE_ME_dev_only_secret_key")
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    secure_cookies: bool = False
    cors_origins: str = "*"

    # --- Datenbank / Cache ---
    database_url: str = "sqlite:///./hermes.db"
    redis_url: Optional[str] = None

    # --- Push Notifications (VAPID) ---
    vapid_private_key: Optional[str] = None
    vapid_public_key: Optional[str] = None
    vapid_email: str = "mailto:admin@example.com"

    # --- Wetter (Open-Meteo, kein Key nötig) ---
    weather_enabled: bool = True
    weather_latitude: float = 52.52
    weather_longitude: float = 13.405
    weather_location_name: str = "Zuhause"

    # --- Connector: Kalender (CalDAV / Nextcloud) ---
    caldav_url: Optional[str] = None
    caldav_username: Optional[str] = None
    caldav_password: Optional[str] = None

    # --- Connector: Aufgaben (Vikunja) ---
    vikunja_url: Optional[str] = None
    vikunja_token: Optional[str] = None

    # --- Connector: Einkauf (KitchenOwl) ---
    kitchenowl_url: Optional[str] = None
    kitchenowl_token: Optional[str] = None

    # --- Connector: Dokumente (Paperless-ngx) ---
    paperless_url: Optional[str] = None
    paperless_token: Optional[str] = None

    # --- Connector: Inventar (Homebox) ---
    homebox_url: Optional[str] = None
    homebox_token: Optional[str] = None

    # --- Connector: Smart Home (Home Assistant) ---
    homeassistant_url: Optional[str] = None
    homeassistant_token: Optional[str] = None

    # --- Connector: Medien (Plex) – aus Legacy Family Hub übernommen ---
    plex_url: Optional[str] = None
    plex_token: Optional[str] = None

    # --- Connector: Hörbücher (Audiobookshelf) ---
    audiobookshelf_url: Optional[str] = None
    audiobookshelf_token: Optional[str] = None

    # --- Connector: Tonies (TeddyCloud, ohne Auth) ---
    teddycloud_url: Optional[str] = None

    # --- Connector: Media-Requests (Overseerr) ---
    overseerr_url: Optional[str] = None
    overseerr_api_key: Optional[str] = None

    # --- Hermes AI ---
    ai_enabled: bool = True
    # OpenAI-kompatibler Endpoint. Für lokale Modelle (Ollama, LM Studio, vLLM)
    # einfach base_url anpassen, z.B. http://localhost:11434/v1
    ai_provider: str = "openai"  # openai | local | none
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: Optional[str] = None
    ai_model: str = "gpt-4o-mini"
    ai_max_tokens: int = 1024

    @property
    def cors_origin_list(self) -> List[str]:
        """CORS Origins als Liste (kommasepariert in der ENV)."""
        raw = (self.cors_origins or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Gecachte Settings-Instanz (Singleton)."""
    return Settings()


settings = get_settings()
