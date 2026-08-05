#!/usr/bin/env bash
# Hermes Family OS – One-Shot-Installer
# Richtet ALLES ein: Abhängigkeiten, Konfiguration (.env), Admin und Start.
#   Lokal  : Python-venv + alle Pakete + optional systemd-Dienst
#   Docker : docker compose up -d --build
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

c()   { if [ -t 1 ]; then printf '\033[%sm%s\033[0m' "$1" "$2"; else printf '%s' "$2"; fi; }
say() { printf '%s\n' "$*"; }
hr()  { say ""; c "1;36" "── $* "; say ""; }

# COMPOSE_PROFILES (aus .env) → Compose-Service-Namen der gebündelten Dienste.
bundle_services() {
  local profs svc="" p
  profs="$(grep -E '^COMPOSE_PROFILES=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"
  for p in ${profs//,/ }; do
    case "$p" in
      agent) svc="$svc hermes-agent hermes-mcp" ;;
      radicale|vikunja|kitchenowl|paperless|homebox) svc="$svc $p" ;;
    esac
  done
  printf '%s' "$svc"
}

# COMPOSE_PROFILES (aus .env) → explizite '--profile X'-Flags (robust über alle
# compose-Versionen, unabhängig davon, ob .env-COMPOSE_PROFILES gelesen wird).
compose_profile_args() {
  local profs args="" p
  profs="$(grep -E '^COMPOSE_PROFILES=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"
  for p in ${profs//,/ }; do [ -n "$p" ] && args="$args --profile $p"; done
  printf '%s' "$args"
}

# Lokaler Modus: startet NUR die gebündelten Dienste (nicht den Core-Container,
# der läuft bare-metal). Docker-Modus braucht das nicht (COMPOSE_PROFILES startet alles mit).
# Stellt sicher, dass Docker + Compose vorhanden sind; bietet Auto-Installation an
# (offizielles get.docker.com-Skript). Gibt 0 zurück, wenn Docker danach nutzbar ist.
ensure_docker() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then return 0; fi
  hr "Docker wird benötigt"
  say "  Die gewählten Dienste laufen als Container – dafür braucht es Docker + Compose."
  local a=""
  read -r -p "Docker jetzt automatisch installieren (offizielles Skript get.docker.com)? [J/n]: " a || true
  if [[ "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    say "  Später manuell:"; c "1" "    curl -fsSL https://get.docker.com | sh"; say ""
    return 1
  fi
  command -v curl >/dev/null 2>&1 || { c "31" "  'curl' fehlt – Docker bitte manuell installieren."; say ""; return 1; }
  say "  Installiere Docker … (das kann ein paar Minuten dauern)"
  $SUDO sh -c "curl -fsSL https://get.docker.com | sh" || { c "31" "  Docker-Installation fehlgeschlagen."; say ""; return 1; }
  $SUDO systemctl enable --now docker >/dev/null 2>&1 || true
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

start_bundles_local() {
  local svc; svc="$(bundle_services)"
  [ -n "${svc// /}" ] || return 0
  ensure_docker || { say "  Nach Docker-Installation starten:  docker compose$(compose_profile_args) up -d --build"; say ""; return 0; }
  hr "Gebündelte Dienste (Docker)"
  say "  Baue & starte:$svc   (Build kann dauern)"
  docker compose up -d --build $svc
  c "32" "  ✅ gestartet."; say ""
  docker compose ps
}

# hermes-agent Setup/Login (Container muss bereits laufen). Nur bei AI_PROVIDER=hermes_agent.
setup_agent() {
  grep -qE '^AI_PROVIDER=hermes_agent$' .env 2>/dev/null || return 0
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1 || return 0
  hr "Nous Hermes Agent – Einrichtung"
  local a=""
  read -r -p "Login + API-Plattform jetzt einrichten (interaktiv)? [J/n]: " a || true
  if [[ ! "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    say "  1) Login (Codex/ChatGPT-Abo oder Nous Portal):"
    docker compose exec hermes-agent hermes setup || true
    say "  2) API-Plattform aktivieren (OpenAI-API :8642):"
    docker compose exec hermes-agent hermes gateway setup || true
    docker compose restart hermes-agent || true
  fi
  say "  Warte auf hermes-agent (API :8642) …"
  local cid ok=0 st
  cid="$(docker compose ps -q hermes-agent 2>/dev/null || true)"
  for _ in $(seq 1 36); do
    st="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || true)"
    [ "$st" = "healthy" ] && { ok=1; break; }
    sleep 5
  done
  if [ "$ok" = "1" ]; then c "32" "  ✅ hermes-agent healthy."; say ""
  else c "33" "  ⚠ noch nicht healthy (${st:-?}).  Logs: docker compose logs -f hermes-agent"; say ""; fi
  a=""
  read -r -p "Haushalts-Tools (MCP) mit hermes verbinden? [J/n]: " a || true
  if [[ ! "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    docker compose exec hermes-agent hermes mcp add hermes-family \
      --transport streamable-http --url http://hermes-mcp:8765/mcp || true
  fi
}

# Hinweise zu gebündelten Web-UIs + Token-Erstellung.
print_bundle_hints() {
  local svc; svc="$(bundle_services)"
  [ -n "${svc// /}" ] || return 0
  hr "Gebündelte Dienste – letzter Schritt"
  say "  Einmal je Web-UI einloggen. Für Vikunja/KitchenOwl/Paperless/Homebox einen"
  say "  API-Token erstellen, in die .env eintragen und dann:"
  c "1" "    docker compose restart hermes"; say ""
  say "  Adressen/Details: docs/SELFHOSTED.md"
}

say ""
c "1;35" "☿  Hermes Family OS – Installer"; say ""

if ! command -v python3 >/dev/null 2>&1; then
  c "31" "python3 wird benötigt (>= 3.11)."; say ""; exit 1
fi

IS_ROOT=0; [ "$(id -u)" = "0" ] && IS_ROOT=1
SUDO=""
if [ "$IS_ROOT" -ne 1 ] && command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi

# --- Installationsart wählen ---
TARGET="local"
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  say ""
  say "Wie möchtest du installieren?"
  say "  1) Lokal auf diesem Host (Python-venv, kein Docker)"
  say "  2) Docker (Compose)"
  sel=""; read -r -p "Auswahl [1/2, Standard 2]: " sel || true
  case "${sel:-2}" in
    1) TARGET="local" ;;
    *) TARGET="docker" ;;
  esac
else
  say "Docker nicht gefunden → lokale Installation (Python-venv)."
fi
export HERMES_INSTALL_TARGET="$TARGET"

# =====================================================================
# Docker-Pfad
# =====================================================================
if [ "$TARGET" = "docker" ]; then
  hr "Konfiguration"
  # VAPID-Erzeugung nutzt 'cryptography' – best effort für den Host-Python.
  python3 -c "import cryptography" >/dev/null 2>&1 || pip3 install --quiet cryptography >/dev/null 2>&1 || true
  python3 backend/scripts/setup.py

  hr "Start (Docker)"
  BUNDLES="$(bundle_services)"
  if [ -n "${BUNDLES// /}" ]; then
    say "  Gebündelte Dienste werden mitgestartet:${BUNDLES}"
  else
    c "33" "  Hinweis: keine Dienste zum Selbst-Installieren gewählt (im Installer je Dienst 'i' tippen)."; say ""
  fi
  # Profile EXPLIZIT übergeben (robust, unabhängig vom .env-Auto-Read).
  docker compose $(compose_profile_args) up -d --build

  a2=""; read -r -p "Admin-Benutzer jetzt anlegen? [J/n]: " a2 || true
  if [[ ! "${a2:-}" =~ ^([nN]|nein|no)$ ]]; then
    docker compose exec hermes python -m scripts.create_admin || true
  fi

  setup_agent          # hermes-agent Login/Plattform (falls installiert)
  print_bundle_hints   # Token-Schritte für die gebündelten Dienste

  hr "Laufende Container"
  docker compose ps

  PORT="$(grep -E '^PORT=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"; PORT="${PORT:-8000}"
  say ""; c "1;32" "Fertig. App: http://localhost:${PORT}"; say ""
  exit 0
fi

# =====================================================================
# Lokaler Pfad – one-shot inkl. ALLER Abhängigkeiten
# =====================================================================
hr "Python-Umgebung & Abhängigkeiten"

# venv-/pip-Modul sicherstellen (Debian/Ubuntu: python3-venv).
if ! python3 -c "import venv, ensurepip" >/dev/null 2>&1; then
  if command -v apt-get >/dev/null 2>&1; then
    say "Installiere python3-venv / python3-pip …"
    $SUDO apt-get update -qq
    $SUDO apt-get install -y -qq python3-venv python3-pip
  else
    c "31" "python3-venv fehlt und kann hier nicht automatisch installiert werden."; say ""
    say "Bitte manuell installieren (z.B. 'apt install python3-venv') und erneut ausführen."
    exit 1
  fi
fi

VENV="$ROOT/backend/.venv"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
PY="$VENV/bin/python"

"$PY" -m pip install --upgrade --quiet pip
say "Installiere Abhängigkeiten (kann einen Moment dauern) …"
"$PY" -m pip install --quiet -r backend/requirements.txt
c "32" "  ✅ Abhängigkeiten installiert."; say ""

hr "Konfiguration"
# Assistent mit venv-Python -> VAPID (cryptography) ist verfügbar.
"$PY" backend/scripts/setup.py

hr "Admin-Benutzer"
a2=""; read -r -p "Admin-Benutzer jetzt anlegen? [J/n]: " a2 || true
if [[ ! "${a2:-}" =~ ^([nN]|nein|no)$ ]]; then
  ( cd backend && "$PY" -m scripts.create_admin ) || true
fi

# Host/Port aus der geschriebenen .env lesen.
PORT="$(grep -E '^PORT=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"; PORT="${PORT:-8000}"
HOSTB="$(grep -E '^HOST=' .env 2>/dev/null | tail -n1 | cut -d= -f2 || true)"; HOSTB="${HOSTB:-0.0.0.0}"

hr "Start"
SERVICE_DONE=0
if command -v systemctl >/dev/null 2>&1 && { [ "$IS_ROOT" = "1" ] || [ -n "$SUDO" ]; }; then
  s1=""; read -r -p "Als systemd-Dienst 'hermes' einrichten und starten (empfohlen)? [J/n]: " s1 || true
  if [[ ! "${s1:-}" =~ ^([nN]|nein|no)$ ]]; then
    UNIT=/etc/systemd/system/hermes.service
    $SUDO tee "$UNIT" >/dev/null <<EOF
[Unit]
Description=Hermes Family OS
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT/backend
ExecStart=$VENV/bin/uvicorn app.main:app --host $HOSTB --port $PORT
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
    $SUDO systemctl daemon-reload
    $SUDO systemctl enable --now hermes
    SERVICE_DONE=1
    say ""; c "32" "  ✅ Dienst 'hermes' läuft."; say ""
    say "     Status:  systemctl status hermes"
    say "     Logs:    journalctl -u hermes -f"
  fi
fi

if [ "$SERVICE_DONE" -ne 1 ]; then
  say "  Manuell starten:"
  c "1" "    cd $ROOT/backend && source .venv/bin/activate"; say ""
  c "1" "    uvicorn app.main:app --host $HOSTB --port $PORT"; say ""
fi

start_bundles_local   # gebündelte Dienste (Docker) starten – Core läuft bare-metal
setup_agent           # hermes-agent Login/Plattform (falls installiert)
print_bundle_hints    # Token-Schritte für die gebündelten Dienste

say ""
c "1;32" "Fertig. App: http://<server-ip>:${PORT}"; say ""
