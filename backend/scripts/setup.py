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

    # KI-Modus
    head("Hermes AI")
    print("  (1) agent  = kompletter NousResearch/hermes-agent als Sidecar (empfohlen)")
    print("  (2) cloud  = OpenAI-kompatibles Cloud-Modell (API-Key)")
    print("  (3) none   = regelbasiert (ohne externes Modell)")
    current = "agent" if env.get("AI_PROVIDER") == "hermes_agent" else ("cloud" if env.get("AI_PROVIDER") in ("openai", "local") else "none")
    mode = ask("KI-Modus (agent/cloud/none)", current).lower()
    env["AI_ENABLED"] = "true"
    env["AI_MAX_TOKENS"] = env.get("AI_MAX_TOKENS", "1024")

    if mode == "agent":
        env["AI_PROVIDER"] = "hermes_agent"
        env["HERMES_AGENT_URL"] = ask("hermes-agent API-URL (…/v1)", env.get("HERMES_AGENT_URL", "http://hermes-agent:8890/v1"))
        env["HERMES_AGENT_DASHBOARD_URL"] = ask("hermes-agent Dashboard-URL", env.get("HERMES_AGENT_DASHBOARD_URL", "http://hermes-agent:9119"))
        env["HERMES_AGENT_MODEL"] = ask("Modell (im Sidecar)", env.get("HERMES_AGENT_MODEL", "default"))
        env["HERMES_AGENT_IMAGE"] = ask("Docker-Image (gepinnt!)", env.get("HERMES_AGENT_IMAGE", "nousresearch/hermes-agent:latest"))
        print(_c("  Start:  docker compose --profile agent up -d", "36"))
        print(_c("  Login (einmalig, interaktiv):", "36"))
        print(_c("    docker compose exec hermes-agent hermes auth add openai --type device-code   # Codex/ChatGPT-Abo", "1"))
        print(_c("    docker compose exec hermes-agent hermes setup --portal                        # Nous Portal", "1"))
        print(_c("  Details: docs/HERMES_AGENT.md", "33"))
    elif mode == "cloud":
        provider = ask("Provider (openai / custom)", env.get("AI_PROVIDER", "openai") if env.get("AI_PROVIDER") in ("openai", "custom") else "openai")
        env["AI_PROVIDER"] = "openai"  # OpenAI-kompatibler Codepfad
        env["AI_BASE_URL"] = ("https://api.openai.com/v1" if provider != "custom"
                              else ask("Base-URL (…/v1)", env.get("AI_BASE_URL", "https://api.openai.com/v1")))
        env["AI_API_KEY"] = ask_secret("API-Key", env.get("AI_API_KEY", ""))
        env["AI_MODEL"] = ask("Modell", env.get("AI_MODEL", "gpt-4o-mini"))
    else:
        env["AI_PROVIDER"] = "none"
        print(_c("  KI läuft im regelbasierten Modus (ohne externes Modell).", "33"))

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
