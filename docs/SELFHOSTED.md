# Dienste selbst installieren (One-Shot)

Der Installer (`./install.sh`) kann die Fach-Dienste **selbst per Docker
installieren** – pro Dienst wählbar:

- **i = installieren** → Hermes startet den Dienst als Container mit.
- **v = verbinden** → du gibst URL + Token eines **bestehenden** Dienstes an.
- **Enter = überspringen**.

**Medien & \*arr werden bewusst NICHT installiert** (Plex, Sonarr, Radarr,
Overseerr, Audiobookshelf, Tonies) – die betreibst du selbst, Hermes verbindet
sich nur. Home Assistant ebenso (nur verbinden).

## Bundle-fähige Dienste

| Dienst | Profil | Port (Host) | Token |
|--------|--------|-------------|-------|
| Kalender (Radicale/CalDAV) | `radicale` | 5232 | kein Token – User/Passwort erzeugt der Installer |
| Aufgaben (Vikunja) | `vikunja` | 3456 | **automatisch** (dauerhafter API-Token) |
| Einkauf (KitchenOwl) | `kitchenowl` | 8082 | **automatisch** (Long-Lived-Token) |
| Dokumente (Paperless-ngx) | `paperless` | 8081 | **automatisch** (DRF-API-Token) |
| Inventar (Homebox) | `homebox` | 7745 | **automatisch** (Login-Token) |
| KI (NousResearch/hermes-agent) | `agent` | 8642 | `hermes setup` (Codex/Nous) – der Installer stößt es an |

Die Auswahl landet als **`COMPOSE_PROFILES`** in der `.env`; Docker Compose liest
das automatisch, `docker compose up -d` startet genau diese Dienste mit.

## Ablauf (One-Shot, volle Automatik)

```bash
./install.sh          # Ziel wählen (lokal/Docker), Dienste je i/v/Enter …
                      # dann VOLLAUTOMATISCH: Deps, .env, Container, API-Tokens, Admin
```

**API-Tokens werden automatisch erzeugt.** Nach dem Start der Container legt der
Installer für Vikunja/KitchenOwl/Paperless/Homebox den ersten Nutzer an, erstellt
einen (möglichst dauerhaften) API-Token und schreibt ihn in die `.env` – ganz ohne
manuelles Einloggen, Token-Kopieren oder Neustarten. Danach liest Hermes die Tokens
direkt ein. Dahinter steckt `backend/scripts/provision_tokens.py`.

- Die Dienste nutzen **einen gemeinsamen Admin-Login** (`BUNDLE_ADMIN_USER` /
  `BUNDLE_ADMIN_PASSWORD` in der `.env`) – damit meldest du dich später auch selbst
  in den Weboberflächen an.
- **Idempotent:** ein zweiter `./install.sh`-Lauf lässt bestehende Tokens in Ruhe.
- **Nachträglich/erneut** (z. B. wenn ein Dienst beim ersten Mal noch nicht bereit
  war):

  ```bash
  cd backend && python -m scripts.provision_tokens            # fehlende Tokens nachziehen
  cd backend && python -m scripts.provision_tokens --force    # alle neu erzeugen
  cd backend && python -m scripts.provision_tokens --only vikunja
  ```

  Bei Docker danach `docker compose up -d --force-recreate hermes`, lokal
  `systemctl restart hermes`.

**Fallback:** Sollte ein Dienst nicht rechtzeitig erreichbar sein, meldet der
Installer das je Dienst und du kannst den Token wie gehabt manuell in der Web-UI
(`http://<PUBLIC_HOST>:<port>`) erstellen und als `<DIENST>_TOKEN` in die `.env`
eintragen.

CalDAV/Radicale braucht **keinen** Token – User/Passwort erzeugt der Installer
(steht in der `.env`, Datei `deploy/radicale/users`).

## URLs (App ↔ Dienst)

- **Docker-Ziel:** die App erreicht Dienste über den Compose-Service-Namen
  (`http://vikunja:3456` …) – der Installer trägt das automatisch ein.
- **Lokales Ziel (bare-metal App):** die App nutzt `http://localhost:<port>`;
  die gebündelten Dienste laufen trotzdem in Docker.

## Reproduzierbarkeit

Die gebündelten Images sind auf `:latest` gesetzt. Für reproduzierbare
Installationen die Tags in `docker-compose.yml` **pinnen**. hermes-agent wird aus
einem **gepinnten** Repo-Commit gebaut (siehe `docs/HERMES_AGENT.md`).
