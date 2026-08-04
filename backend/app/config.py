"""Zentrale Konfiguration für Hermes Family OS.

Alle Einstellungen werden aus Umgebungsvariablen (oder einer ``.env`` Datei)
gelesen. Es werden bewusst KEINE Secrets im Code hinterlegt. Jeder Connector
ist optional: Fehlt die Konfiguration, läuft Hermes im "Demo-Modus" und der
betreffende Baustein liefert leere/Beispiel-Daten statt einen Fehler zu werfen.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-Wurzel (…/config.py -> app -> backend -> root), damit die .env unabhängig
# vom Arbeitsverzeichnis gefunden wird (der Installer schreibt sie in die Wurzel).
_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Applikationsweite Einstellungen (env-driven)."""

    model_config = SettingsConfigDict(
        env_file=(str(_ROOT / ".env"), str(_ROOT / "backend" / ".env"), ".env"),
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

    # --- Connector: Serien (Sonarr) ---
    sonarr_url: Optional[str] = None
    sonarr_api_key: Optional[str] = None
    # Optionale Defaults fürs Hinzufügen (sonst erstes vorhandenes Profil/Root).
    sonarr_quality_profile_id: Optional[int] = None
    sonarr_root_folder: Optional[str] = None

    # --- Connector: Filme (Radarr) ---
    radarr_url: Optional[str] = None
    radarr_api_key: Optional[str] = None
    radarr_quality_profile_id: Optional[int] = None
    radarr_root_folder: Optional[str] = None

    # --- Homelab-Status-Board (generisch, up/down + Link) ---
    # JSON-Liste, z.B. [{"name":"SABnzbd","url":"http://…:8080","category":"automation","icon":"📥"}]
    homelab_services: str = ""

    # --- Hermes AI ---
    # Der Chat ist ein reiner Client zum hermes-agent-Sidecar. Sinnvolle Werte:
    #   hermes_agent = mit dem Sidecar verbunden (er ist der Agent; wir relayen nur)
    #   none         = Chat inaktiv (klarer Hinweis, kein Wort-Matcher/eigener Agent)
    ai_enabled: bool = True
    ai_provider: str = "none"
    ai_max_tokens: int = 1024
    # Modell für Sprach-Transkription (OpenAI-/Whisper-kompatibel, via Sidecar)
    ai_transcribe_model: str = "whisper-1"
    # Vestigiale Direktmodell-Felder (nicht mehr für den Chat genutzt; nur als
    # optionaler Transkriptions-Endpoint, falls kein Sidecar transkribiert).
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: Optional[str] = None
    ai_model: str = "gpt-4o-mini"

    # --- NousResearch/hermes-agent (Sidecar) ---
    # OpenAI-kompatibler API-Server des Sidecars (…/v1), z.B. http://hermes-agent:8890/v1
    hermes_agent_url: Optional[str] = None
    # Web-Dashboard des Sidecars (für die eingebettete Voll-UI), z.B. http://hermes-agent:9119
    hermes_agent_dashboard_url: Optional[str] = None
    # Modellname, den der Sidecar nutzen soll (er verwaltet Provider/Login selbst)
    hermes_agent_model: str = "default"
    # Optionaler Shared-Secret/Token für den API-Server (falls konfiguriert)
    hermes_agent_token: Optional[str] = None

    # --- MCP-Server (Haushalts-Werkzeuge an hermes-agent) ---
    # Exponiert unsere Tools als MCP-Server, damit hermes-agent Einkauf/Kalender/
    # Licht/Finanzen … steuern kann. Als eigener Dienst: python -m app.mcp.server
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8765
    # Rolle, mit der der Familien-Agent handelt (guest<child<partner<admin).
    mcp_role: str = "partner"

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

    @property
    def homelab_service_list(self) -> List[dict]:
        """Homelab-Dienste fürs Status-Board (JSON in HOMELAB_SERVICES)."""
        raw = (self.homelab_services or "").strip()
        if not raw:
            return []
        import json

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        out: List[dict] = []
        for s in data if isinstance(data, list) else []:
            if isinstance(s, dict) and s.get("name") and s.get("url"):
                out.append(
                    {
                        "name": str(s["name"]),
                        "url": str(s["url"]),
                        "category": str(s.get("category", "service")),
                        "icon": str(s.get("icon", "🖥️")),
                    }
                )
        return out


@lru_cache
def get_settings() -> Settings:
    """Gecachte Settings-Instanz (Singleton)."""
    return Settings()


settings = get_settings()
