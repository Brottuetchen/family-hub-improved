#!/usr/bin/env bash
# Hermes Family OS – Installer (Komfort-Wrapper um den Setup-Assistenten)
set -euo pipefail
cd "$(dirname "$0")"

echo "☿  Hermes Family OS – Installer"
echo

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 wird benötigt." >&2
  exit 1
fi

# VAPID-Erzeugung nutzt 'cryptography' – falls möglich bereitstellen (best effort).
python3 -c "import cryptography" >/dev/null 2>&1 || pip3 install --quiet cryptography >/dev/null 2>&1 || true

# Interaktiver Assistent: fragt IPs, API-Keys und Zugangsdaten ab und schreibt .env
python3 backend/scripts/setup.py

# Optional direkt mit Docker starten
if command -v docker >/dev/null 2>&1; then
  read -r -p "Jetzt mit Docker starten (docker compose up -d --build)? [j/N]: " ans
  if [[ "${ans,,}" =~ ^(j|ja|y|yes)$ ]]; then
    docker compose up -d --build
    echo
    read -r -p "Admin-Benutzer jetzt anlegen? [J/n]: " a2
    if [[ ! "${a2,,}" =~ ^(n|nein|no)$ ]]; then
      docker compose exec hermes python -m scripts.create_admin
    fi
    echo
    echo "Fertig. App: http://localhost:8000"
  fi
else
  echo "Docker nicht gefunden – App manuell starten (siehe Hinweise oben)."
fi
