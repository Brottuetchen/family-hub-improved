"""Interaktiver Installer für Hermes Family OS.

Fragt alle nötigen URLs/IPs, API-Keys und Zugangsdaten ab und schreibt eine
fertige ``.env``. Secrets werden automatisch erzeugt (SECRET_KEY, VAPID).

Nutzung:
    python backend/scripts/setup.py            # interaktiv
    ./install.sh                               # Komfort-Wrapper (+ Docker)

Der Installer benötigt nur die Standardbibliothek (VAPID-Erzeugung nutzt
optional 'cryptography'; fehlt es, bleibt VAPID leer und kann später erzeugt
werden).
"""

from __future__ import annotations

import getpass
import json
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

# Connector-Definitionen: (ENV-Key, Label, ist_secret)
CONNECTORS = [
    ("Kalender (Nextcloud/CalDAV)", [
        ("CALDAV_URL", "URL (z.B. https://cloud.example.com/remote.php/dav)", False),
        ("CALDAV_USERNAME", "Benutzername", False),
        ("CALDAV_PASSWORD", "Passwort / App-Passwort", True),
    ]),
    ("Aufgaben (Vikunja)", [
        ("VIKUNJA_URL", "URL (z.B. https://vikunja.example.com)", False),
        ("VIKUNJA_TOKEN", "API-Token", True),
    ]),
    ("Einkauf (KitchenOwl)", [
        ("KITCHENOWL_URL", "URL", False),
        ("KITCHENOWL_TOKEN", "API-Token", True),
    ]),
    ("Dokumente (Paperless-ngx)", [
        ("PAPERLESS_URL", "URL", False),
        ("PAPERLESS_TOKEN", "API-Token", True),
    ]),
    ("Inventar (Homebox)", [
        ("HOMEBOX_URL", "URL", False),
        ("HOMEBOX_TOKEN", "API-Token", True),
    ]),
    ("Smart Home (Home Assistant)", [
        ("HOMEASSISTANT_URL", "URL (z.B. http://192.168.1.10:8123)", False),
        ("HOMEASSISTANT_TOKEN", "Long-Lived Access Token", True),
    ]),
    ("Medien (Plex)", [
        ("PLEX_URL", "URL (z.B. http://192.168.1.7:32400)", False),
        ("PLEX_TOKEN", "X-Plex-Token", True),
    ]),
    ("Hörbücher (Audiobookshelf)", [
        ("AUDIOBOOKSHELF_URL", "URL", False),
        ("AUDIOBOOKSHELF_TOKEN", "API-Token", True),
    ]),
    ("Tonies (TeddyCloud)", [
        ("TEDDYCLOUD_URL", "URL (kein Token nötig)", False),
    ]),
    ("Media-Requests (Overseerr)", [
        ("OVERSEERR_URL", "URL", False),
        ("OVERSEERR_API_KEY", "API-Key", True),
    ]),
    ("Serien (Sonarr)", [
        ("SONARR_URL", "URL (z.B. http://192.168.1.71:8989)", False),
        ("SONARR_API_KEY", "API-Key (Settings → General)", True),
    ]),
    ("Filme (Radarr)", [
        ("RADARR_URL", "URL (z.B. http://192.168.1.73:7878)", False),
        ("RADARR_API_KEY", "API-Key (Settings → General)", True),
    ]),
]


# --- I/O-Helfer ---

def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def head(title: str) -> None:
    print("\n" + _c(f"── {title} ", "1;36") + _c("─" * max(2, 46 - len(title)), "36"))


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"  {prompt}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val or default


def ask_secret(prompt: str, default: str = "") -> str:
    hint = " [bereits gesetzt – Enter behält]" if default else ""
    try:
        val = getpass.getpass(f"  {prompt}{hint}: ").strip()
    except (EOFError, getpass.GetPassWarning):
        val = ""
    return val or default


def ask_yesno(prompt: str, default: bool = False) -> bool:
    d = "J/n" if default else "j/N"
    try:
        val = input(f"  {prompt} [{d}]: ").strip().lower()
    except EOFError:
        return default
    if not val:
        return default
    return val in ("j", "ja", "y", "yes")


# --- .env laden/schreiben ---

def load_env(path: Path) -> dict:
    data: dict = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        data[key.strip()] = val.strip()
    return data


def gen_vapid() -> tuple[str, str]:
    try:
        sys.path.insert(0, str(ROOT / "backend"))
        from scripts.generate_vapid import generate_keys

        return generate_keys()
    except Exception as exc:  # noqa: BLE001
        print(_c(f"  (VAPID übersprungen: {exc} – später mit generate_vapid erzeugen)", "33"))
        return "", ""


def write_env(path: Path, env: dict) -> None:
    if path.exists():
        backup = path.parent / ".env.bak"
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        print(_c(f"  Vorherige .env gesichert unter {backup}", "33"))

    order = [
        ("App / Server", ["ENVIRONMENT", "HOST", "PORT", "LOG_LEVEL", "TIMEZONE", "VERIFY_TLS"]),
        ("Security", ["SECRET_KEY", "SECURE_COOKIES", "CORS_ORIGINS"]),
        ("Datenbank", ["DATABASE_URL", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "REDIS_URL"]),
        ("Push (VAPID)", ["VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_EMAIL"]),
        ("Wetter", ["WEATHER_ENABLED", "WEATHER_LATITUDE", "WEATHER_LONGITUDE", "WEATHER_LOCATION_NAME"]),
        ("Hermes AI", ["AI_ENABLED", "AI_PROVIDER", "AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "AI_MAX_TOKENS", "AI_TRANSCRIBE_MODEL"]),
        ("Hermes Agent (Sidecar)", ["HERMES_AGENT_URL", "HERMES_AGENT_DASHBOARD_URL", "HERMES_AGENT_MODEL", "HERMES_AGENT_TOKEN", "HERMES_AGENT_IMAGE"]),
        ("Connectoren", [k for _, fields in CONNECTORS for (k, _, _) in fields]),
        ("Homelab-Status-Board", ["HOMELAB_SERVICES"]),
    ]
    lines = ["# Hermes Family OS – erzeugt vom Installer (backend/scripts/setup.py)", ""]
    written = set()
    for section, keys in order:
        # Leere Werte NICHT schreiben – sonst würden Code-Defaults überschrieben.
        section_lines = []
        for key in keys:
            written.add(key)
            val = env.get(key, "")
            if val != "":
                section_lines.append(f"{key}={val}")
        if section_lines:
            lines.append(f"# --- {section} ---")
            lines.extend(section_lines)
            lines.append("")
    extra = [f"{k}={env[k]}" for k in env if k not in written and env[k] != ""]
    if extra:
        lines.append("# --- Weitere ---")
        lines.extend(extra)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --- Hauptablauf ---

def main() -> int:
    print(_c("\n☿  Hermes Family OS – Installer\n", "1;35"))
    print("Ich frage alle nötigen URLs, API-Keys und Zugangsdaten ab und schreibe eine .env.")
    print("Leer lassen = überspringen. Enter übernimmt den [Vorgabewert].")

    env = load_env(ENV_PATH)
    if env:
        print(_c(f"\nBestehende {ENV_PATH} gefunden – Werte werden als Vorgaben genutzt.", "33"))

    # Core
    head("Grundeinstellungen")
    env["ENVIRONMENT"] = ask("Umgebung (development/production)", env.get("ENVIRONMENT", "production"))
    env["TIMEZONE"] = ask("Zeitzone", env.get("TIMEZONE", "Europe/Berlin"))
    env["CORS_ORIGINS"] = ask("Erlaubte Origins (Komma-getrennt) oder *", env.get("CORS_ORIGINS", "*"))
    env["SECURE_COOKIES"] = "true" if ask_yesno("Läuft hinter HTTPS (SECURE_COOKIES)?", env.get("SECURE_COOKIES") == "true") else "false"
    env["HOST"] = env.get("HOST", "0.0.0.0")
    env["PORT"] = env.get("PORT", "8000")
    env["LOG_LEVEL"] = env.get("LOG_LEVEL", "info")
    env["VERIFY_TLS"] = "false" if ask_yesno("Selbst-signierte Zertifikate im Netzwerk (TLS nicht prüfen)?", env.get("VERIFY_TLS") == "false") else "true"

    # Secret
    if env.get("SECRET_KEY") and env["SECRET_KEY"] != "CHANGE_ME_generate_a_long_random_secret":
        if ask_yesno("SECRET_KEY neu erzeugen?", False):
            env["SECRET_KEY"] = secrets.token_urlsafe(48)
    else:
        env["SECRET_KEY"] = secrets.token_urlsafe(48)
        print(_c("  SECRET_KEY automatisch erzeugt.", "32"))

    # Wetter
    head("Wetter (Open-Meteo, kein Key)")
    env["WEATHER_ENABLED"] = "true"
    env["WEATHER_LOCATION_NAME"] = ask("Ortsname", env.get("WEATHER_LOCATION_NAME", "Zuhause"))
    env["WEATHER_LATITUDE"] = ask("Breitengrad", env.get("WEATHER_LATITUDE", "52.52"))
    env["WEATHER_LONGITUDE"] = ask("Längengrad", env.get("WEATHER_LONGITUDE", "13.405"))

    # Installations-Ziel (bestimmt v.a. den Datenbank-Host).
    # install.sh setzt HERMES_INSTALL_TARGET; sonst interaktiv erfragen.
    target = (os.environ.get("HERMES_INSTALL_TARGET") or "").strip().lower()
    if target not in ("local", "docker"):
        target = "docker" if ask_yesno(
            "Läuft Hermes in Docker/Compose (nein = lokal auf diesem Host)?", True
        ) else "local"

    # Datenbank
    head("Datenbank")
    if target == "docker":
        use_pg = ask_yesno(
            "PostgreSQL nutzen (empfohlen, sonst SQLite)?",
            env.get("DATABASE_URL", "").startswith("postgres") or bool(env.get("POSTGRES_PASSWORD")),
        )
        if use_pg:
            env["POSTGRES_USER"] = ask("Postgres-Benutzer", env.get("POSTGRES_USER", "hermes"))
            env["POSTGRES_PASSWORD"] = ask_secret("Postgres-Passwort", env.get("POSTGRES_PASSWORD", "")) or secrets.token_urlsafe(16)
            env["POSTGRES_DB"] = ask("Postgres-Datenbank", env.get("POSTGRES_DB", "hermes"))
            # Im Compose-Netz ist der DB-Host der Service-Name 'db'.
            env["DATABASE_URL"] = (
                f"postgresql+psycopg2://{env['POSTGRES_USER']}:{env['POSTGRES_PASSWORD']}@db:5432/{env['POSTGRES_DB']}"
            )
        else:
            env["DATABASE_URL"] = "sqlite:///./hermes.db"
    else:  # local / bare-metal
        print("  Lokal ist SQLite ohne Zusatzdienst am einfachsten (empfohlen).")
        use_pg = ask_yesno(
            "Externe PostgreSQL-DB nutzen (sonst SQLite)?",
            env.get("DATABASE_URL", "").startswith("postgres"),
        )
        if use_pg:
            # WICHTIG: echte Host-Adresse, NICHT 'db' (das gibt es nur in Docker).
            host = ask("Postgres-Host (echte Adresse, nicht 'db')", "localhost")
            port = ask("Postgres-Port", "5432")
            user = ask("Postgres-Benutzer", env.get("POSTGRES_USER", "hermes"))
            pw = ask_secret("Postgres-Passwort", env.get("POSTGRES_PASSWORD", ""))
            dbname = ask("Postgres-Datenbank", env.get("POSTGRES_DB", "hermes"))
            env["DATABASE_URL"] = f"postgresql+psycopg2://{user}:{pw}@{host}:{port}/{dbname}"
        else:
            env["DATABASE_URL"] = "sqlite:///./hermes.db"

    # KI: der echte NousResearch/hermes-agent ist das Gehirn.
    # Das Chatfenster ist NUR ein Client dazu (kein eigener Agent, kein Wort-Matcher).
    head("Hermes AI (NousResearch/hermes-agent)")
    print("  Der Chat spricht ausschließlich den hermes-agent-Sidecar an:")
    print("  seine Tools/Skills/Memory/Voice + Steuerung unserer Module via MCP.")
    env["AI_MAX_TOKENS"] = env.get("AI_MAX_TOKENS", "1024")
    if ask_yesno("hermes-agent verbinden (empfohlen)?", env.get("AI_PROVIDER") == "hermes_agent"):
        env["AI_ENABLED"] = "true"
        env["AI_PROVIDER"] = "hermes_agent"
        # OpenAI-kompatibler API-Server des Sidecars, Default-Port 8642.
        env["HERMES_AGENT_URL"] = ask("hermes-agent API-URL (…/v1)", env.get("HERMES_AGENT_URL", "http://hermes-agent:8642/v1"))
        env["HERMES_AGENT_DASHBOARD_URL"] = ask("Dashboard-URL (optional, leer = keins)", env.get("HERMES_AGENT_DASHBOARD_URL", ""))
        env["HERMES_AGENT_MODEL"] = ask("Modell (im Sidecar)", env.get("HERMES_AGENT_MODEL", "default"))
        # Bearer-Token = API_SERVER_KEY des Sidecars; automatisch erzeugen, wenn leer.
        env["HERMES_AGENT_TOKEN"] = env.get("HERMES_AGENT_TOKEN") or secrets.token_urlsafe(32)
        env["AI_TRANSCRIBE_MODEL"] = ask("Transkriptions-Modell (Voice)", env.get("AI_TRANSCRIBE_MODEL", "whisper-1"))
        print(_c("  Der Installer kann den Sidecar bauen/starten und den Login anstoßen (Docker nötig).", "36"))
        print(_c("  Setup/Login (einmalig, interaktiv):", "36"))
        print(_c("    docker compose exec -it hermes-agent hermes setup            # Wizard (Codex/ChatGPT-Abo)", "1"))
        print(_c("    docker compose exec -it hermes-agent hermes setup --portal   # Nous Portal", "1"))
        print(_c("  Details: docs/HERMES_AGENT.md", "33"))
    else:
        env["AI_ENABLED"] = "false"
        env["AI_PROVIDER"] = "none"
        print(_c("  Ohne hermes-agent bleibt das Chatfenster inaktiv (klarer Hinweis statt Fake-Antwort).", "33"))

    # Push
    head("Push-Benachrichtigungen (VAPID)")
    if not env.get("VAPID_PUBLIC_KEY") or ask_yesno("VAPID-Schlüssel neu erzeugen?", False):
        priv, pub = gen_vapid()
        if priv and pub:
            env["VAPID_PRIVATE_KEY"], env["VAPID_PUBLIC_KEY"] = priv, pub
            print(_c("  VAPID-Schlüssel erzeugt.", "32"))
    env["VAPID_EMAIL"] = ask("Kontakt-E-Mail (mailto:)", env.get("VAPID_EMAIL", "mailto:admin@example.com"))

    # Connectoren
    head("Connectoren (Fachsysteme)")
    print("  Jeder Connector ist optional – nur einrichten, was du nutzt.\n")
    for title, fields in CONNECTORS:
        has_existing = any(env.get(k) for k, _, _ in fields)
        if not ask_yesno(f"{title} einrichten?", has_existing):
            continue
        for key, label, secret in fields:
            cur = env.get(key, "")
            env[key] = ask_secret(label, cur) if secret else ask(label, cur)

    # Homelab-Status-Board (generisch: up/down + Link, für Dienste ohne tiefe Integration)
    head("Homelab-Status-Board (optional)")
    print("  Up/Down-Kacheln + Links für Dienste ohne eigene Integration (SABnzbd, Immich, Trilium …).")
    services = []
    if env.get("HOMELAB_SERVICES"):
        try:
            services = json.loads(env["HOMELAB_SERVICES"]) or []
        except (json.JSONDecodeError, TypeError):
            services = []
    if ask_yesno("Dienste fürs Status-Board hinzufügen?", bool(services)):
        if services and ask_yesno(f"{len(services)} vorhandene verwerfen und neu erfassen?", False):
            services = []
        while True:
            name = ask("Dienst-Name (leer = fertig)")
            if not name:
                break
            url = ask("URL (z.B. http://192.168.1.90:8080)")
            if not url:
                continue
            services.append({
                "name": name,
                "url": url,
                "category": ask("Kategorie", "service"),
                "icon": ask("Icon (Emoji)", "🖥️"),
            })
    if services:
        env["HOMELAB_SERVICES"] = json.dumps(services, separators=(",", ":"), ensure_ascii=False)

    # Schreiben
    head("Speichern")
    write_env(ENV_PATH, env)
    print(_c(f"  ✅ Konfiguration geschrieben: {ENV_PATH}", "1;32"))

    # Nächste Schritte
    head("Nächste Schritte")
    port = env.get("PORT", "8000")
    if target == "docker":
        print("  Mit Docker starten:")
        print(_c("    docker compose up -d --build", "1"))
        print(_c("    docker compose exec hermes python -m scripts.create_admin", "1"))
        print(f"\n  App danach unter http://localhost:{port}\n")
    else:
        print("  Lokal starten (venv):")
        print(_c("    cd backend && source .venv/bin/activate", "1"))
        print(_c("    python -m scripts.create_admin", "1"))
        print(_c(f"    uvicorn app.main:app --host 0.0.0.0 --port {port}", "1"))
        print(_c("\n  Tipp: ./install.sh erledigt venv, Abhängigkeiten, Admin und Dienst automatisch.", "33"))
        print(f"\n  App danach unter http://<server-ip>:{port}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
