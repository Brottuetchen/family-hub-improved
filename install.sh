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

# Baut/startet den NousResearch/hermes-agent-Sidecar und stößt das Setup/Login an.
# Nur relevant, wenn in der .env AI_PROVIDER=hermes_agent gesetzt ist.
bring_up_agent() {
  grep -qE '^AI_PROVIDER=hermes_agent$' .env 2>/dev/null || return 0
  hr "Nous Hermes Agent (Sidecar)"
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    say "  Docker (compose) nicht gefunden – der hermes-agent-Sidecar braucht Docker."
    say "  Bare-metal-Alternative (offizieller Installer + Setup):"
    c "1" "    curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash && hermes setup"; say ""
    say "  Danach HERMES_AGENT_URL auf den API-Server zeigen lassen (…:8642/v1)."
    return 0
  fi
  local a=""
  read -r -p "hermes-agent jetzt aus dem Repo BAUEN & starten (großer Build ~610 MB)? [J/n]: " a || true
  if [[ "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    say "  Später:  docker compose --profile agent up -d --build"
    return 0
  fi
  say "  Baue & starte hermes-agent + hermes-mcp … (Build kann dauern)"
  docker compose --profile agent up -d --build
  c "32" "  ✅ Container gebaut/gestartet."; say ""

  # Einmalige Einrichtung: Login + API-Plattform (der OpenAI-API-Server ist eine
  # Gateway-Plattform -> muss aktiviert werden).
  a=""
  read -r -p "Jetzt einrichten/einloggen (interaktiv)? [J/n]: " a || true
  if [[ ! "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    say "  1) Login (Codex/ChatGPT-Abo oder Nous Portal):"
    docker compose exec hermes-agent hermes setup || true
    say "  2) API-Plattform aktivieren (OpenAI-API auf :8642):"
    docker compose exec hermes-agent hermes gateway setup || true
    docker compose restart hermes-agent || true
  fi

  # Auf Health warten (API :8642 muss auf /v1/models antworten).
  say "  Warte auf hermes-agent (API :8642) …"
  local cid ok=0 st
  cid="$(docker compose ps -q hermes-agent 2>/dev/null || true)"
  for _ in $(seq 1 36); do
    st="$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || true)"
    [ "$st" = "healthy" ] && { ok=1; break; }
    sleep 5
  done
  if [ "$ok" = "1" ]; then
    c "32" "  ✅ hermes-agent ist healthy – die API antwortet."; say ""
  else
    c "33" "  ⚠ hermes-agent noch nicht healthy (Status: ${st:-unbekannt})."; say ""
    say "    Logs:            docker compose logs -f hermes-agent"
    say "    API-Plattform:   docker compose exec hermes-agent hermes gateway setup"
    say "    Danach:          docker compose restart hermes-agent"
  fi

  # Haushalts-Tools (MCP) mit hermes verbinden.
  a=""
  read -r -p "Haushalts-Tools (MCP) jetzt mit hermes verbinden? [J/n]: " a || true
  if [[ ! "${a:-}" =~ ^([nN]|nein|no)$ ]]; then
    docker compose exec hermes-agent hermes mcp add hermes-family \
      --transport streamable-http --url http://hermes-mcp:8765/mcp || true
  fi
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
  docker compose up -d --build

  a2=""; read -r -p "Admin-Benutzer jetzt anlegen? [J/n]: " a2 || true
  if [[ ! "${a2:-}" =~ ^([nN]|nein|no)$ ]]; then
    docker compose exec hermes python -m scripts.create_admin || true
  fi

  bring_up_agent

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

bring_up_agent

say ""
c "1;32" "Fertig. App: http://<server-ip>:${PORT}"; say ""
