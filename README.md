# ☿ Hermes Family OS

**Das digitale Betriebssystem eurer Familie.**

Hermes ist keine weitere To-do-App, sondern eine **intelligente Schicht über euren
bereits vorhandenen self-hosted Diensten**. Termine, Aufgaben, Einkäufe, Dokumente,
Finanzen, Erinnerungen, Smart Home und KI – zusammengeführt in *einer* Oberfläche,
ohne die spezialisierten Fachsysteme zu ersetzen.

> Der Benutzer arbeitet ausschließlich mit Hermes. Im Hintergrund kommuniziert
> Hermes über APIs mit Nextcloud, Vikunja, KitchenOwl, Paperless, Home Assistant & Co.
> **Daten werden möglichst nicht doppelt gespeichert.**

---

## Was Hermes anders macht

- **Eine App statt zehn** – ein Dashboard für das ganze Familienleben.
- **KI, die mitdenkt** – nicht nur Chat, sondern *Werkzeuge*:
  - „Milch ist leer" → Einkaufsliste ergänzen
  - „Erinnere mich heute Abend an den Müll" → Erinnerung anlegen
  - „Morgen regnet es" → Outdoor-Pläne hinterfragen
  - „Carina hat bald Geburtstag" → Geschenkideen sammeln
- **Connector-Architektur** – jedes Fachsystem wird über einen Connector angebunden.
  Nicht konfiguriert? Hermes läuft trotzdem (Graceful Degradation).

---

## Architektur

```
                          Hermes UI  (PWA / React-ready)
                               │
        ───────────────────────┼───────────────────────────
                               │
                        Hermes Backend (FastAPI)
             Dashboard · KI-Agent · Auth/Rollen · Push · Suche
                               │
                     ┌─────────┴──────────┐
                     │  Connector-Layer   │
     ┌───────┬───────┼───────┬───────┬────┴───┬─────────┬────────┐
   Kalender Aufgaben Einkauf Dokumente Inventar SmartHome Wetter  Medien
     │        │        │        │        │        │        │        │
  Nextcloud Vikunja KitchenOwl Paperless Homebox  HA    Open-Meteo Plex
```

Details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)

---

## Module & Status (Phase 1 MVP)

| Modul            | Connector / Quelle      | Status |
|------------------|-------------------------|--------|
| Dashboard        | aggregiert alle Module  | ✅ funktionsfähig |
| Kalender         | CalDAV / Nextcloud      | ✅ (Connector) |
| Feiertage        | Hermes (berechnet)      | ✅ deutsche, bundesweit |
| Aufgaben         | Vikunja                 | ✅ (lesen + anlegen) |
| Einkauf          | KitchenOwl              | ✅ (lesen + hinzufügen) |
| Essensplanung    | Hermes (eigen)          | ✅ Wochenplan → Einkaufsliste |
| Erinnerungen     | Hermes (eigen)          | ✅ voll + Auto-Push bei Fälligkeit |
| Pakete           | Hermes (eigen)          | ✅ Carrier-Erkennung + Tracking-Links |
| Dokumente        | Paperless-ngx           | ✅ lesen + Suche + Fristerkennung |
| Finanzen         | Hermes (eigen)          | ✅ Daueraufträge + Fixkosten |
| Inventar         | Homebox                 | ✅ (lesen + Suche) |
| Wartung          | Hermes (eigen)          | ✅ Pläne + Fälligkeits-Reschedule |
| Smart Home       | Home Assistant          | ✅ (Übersicht + Steuerung) |
| Wetter           | Open-Meteo (kein Key)   | ✅ voll |
| Medien / Audio   | Plex · Audiobookshelf · TeddyCloud · Overseerr | ✅ „Läuft gerade" + Requests |
| Familie & Rollen | Hermes (eigen)          | ✅ admin/partner/kind/gast |
| Globale Suche    | alle Connectors         | ✅ |
| Hermes AI        | OpenAI-kompatibel/lokal | ✅ Tools + Fallback + Spracheingabe |
| Push             | Web Push (VAPID)        | ✅ inkl. Hintergrund-Scheduler |

Fahrplan der weiteren Phasen: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## Schnellstart

### Variante A – Installer (am einfachsten)

Der geführte Installer fragt alle URLs/IPs, API-Keys und Zugangsdaten ab,
erzeugt `SECRET_KEY` und VAPID-Schlüssel automatisch und schreibt die `.env`:

```bash
./install.sh
# alternativ nur den Assistenten:  python3 backend/scripts/setup.py
```
Der Installer ist **one-shot**: du wählst *lokal* (Python-venv) oder *Docker*.
Er installiert **alle** Abhängigkeiten, schreibt die `.env`, legt den Admin an und
startet Hermes – lokal auf Wunsch als `systemd`-Dienst.

### Variante B – Docker manuell

```bash
cp .env.example .env
# SECRET_KEY setzen, gewünschte Connectors konfigurieren
docker compose up -d --build

# Ersten Admin anlegen
docker compose exec hermes python -m scripts.create_admin
# optional: Demo-Daten
docker compose exec hermes python -m scripts.seed_demo
```

App: http://localhost:8000

### Variante C – Lokal (Python 3.11+, ohne Docker)

Am einfachsten via `./install.sh` (Option **„Lokal"**) – er legt die venv an,
installiert **alle** Abhängigkeiten und richtet optional einen `systemd`-Dienst ein.
Manuell:

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python scripts/setup.py              # .env schreiben (Ziel „lokal" -> SQLite)
python -m scripts.create_admin       # Admin anlegen
python -m scripts.seed_demo          # optional: Demo-Daten

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

> Lokal ist **SQLite** der Standard (`DATABASE_URL=sqlite:///./hermes.db`).
> Der Host `db` in `DATABASE_URL` funktioniert **nur** in docker-compose – für
> Postgres bare-metal die echte Host-Adresse eintragen.

App: http://localhost:8000 · API-Docs: http://localhost:8000/docs

---

## Konfiguration

Alles läuft über Umgebungsvariablen (`.env`) – **keine Secrets im Code**.
Jeder Connector ist optional; fehlt er, bleibt das Modul im „nicht konfiguriert"-Zustand,
der Rest funktioniert normal.

```env
# Beispiel: Aufgaben anbinden
VIKUNJA_URL=https://vikunja.example.com
VIKUNJA_TOKEN=xxxxx

# Beispiel: KI (Cloud, OpenAI-kompatibel)
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini
```

Vollständige Liste: [`.env.example`](.env.example) · Connector-Doku: [`docs/CONNECTORS.md`](docs/CONNECTORS.md)

---

## Hermes AI

Vier Betriebsmodi (`AI_PROVIDER`):

- **`hermes_agent` (empfohlen):** der komplette [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
  läuft als **Sidecar** und ist das eigentliche Gehirn (Skills/Selbstlernen, Memory,
  40+ Tools, Subagents, **Voice**, **Abo-Login inkl. Codex/ChatGPT & Nous Portal**).
  Nutzung über unsere Oberfläche: **„Assistent"** (Chat + Voice-Messages) und
  **„Hermes Agent"** (sein volles Dashboard, eingebettet hinter unserem Login).
  → **[docs/HERMES_AGENT.md](docs/HERMES_AGENT.md)**
- **`openai` / `local`:** eigenes OpenAI-kompatibles Modell; unser Agent führt die
  Tool-Schleife selbst (23 Werkzeuge: Einkauf, Kalender, Smart Home, Finanzen …).
- **`none`:** regelbasierter Fallback – „Bestell Milch" / „Was steht heute an?"
  funktionieren **auch ohne Modell**, offline.

**Voice-Messages:** 🎙 im „Assistent" nimmt auf → Transkription → normaler Chat.

---

## Tech-Stack

- **Backend:** FastAPI · SQLAlchemy · Pydantic · httpx · JWT-Auth · Web Push
- **Datenbank:** SQLite (Dev) / PostgreSQL (Prod) · Redis (optional)
- **Frontend:** PWA (offlinefähig, installierbar, Push, Dark Mode). Die API ist
  bewusst frontend-agnostisch – ein Next.js/React-Frontend kann direkt andocken.
- **Deployment:** Docker Compose · Traefik/Nginx davor · Authentik/OAuth2 optional

---

## Projektstruktur

```
backend/
  app/
    main.py            # App-Assembly
    config.py          # Settings (env-driven)
    core/              # database, security (Auth/Rollen), logging
    models/            # SQLAlchemy: user, family, reminder, package, ...
    connectors/        # DIE intelligente Schicht (base, registry, + je System)
    services/          # notifications (Push), insights (proaktive Hinweise)
    ai/                # llm, tools, agent (Hermes AI)
    routers/           # dashboard, calendar, tasks, shopping, ai, ...
  scripts/             # create_admin, seed_demo, generate_vapid
public/                # PWA-Frontend
docs/                  # Architektur, Roadmap, Connectors, Deployment
docker-compose.yml
```

---

## Sicherheit

- Rollenmodell: **admin · partner · kind · gast** (eigene Rechte je Rolle).
- JWT Access-/Refresh-Tokens, Rate-Limiting bei Login, HTTP-only Cookies.
- ⚠️ **In Produktion `SECRET_KEY` setzen** und Connector-Tokens nur in `.env`/Secrets halten.

---

## Credits

Entwickelt von Constantin Trapp · Homelab: Proxmox VE · Lizenz: MIT
