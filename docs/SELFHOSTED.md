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

| Dienst | Profil | Port (Host) | Login/Token |
|--------|--------|-------------|-------------|
| Kalender (Radicale/CalDAV) | `radicale` | 5232 | User/Passwort erzeugt der Installer (in `.env`) |
| Aufgaben (Vikunja) | `vikunja` | 3456 | nach 1. Login **API-Token** erstellen |
| Einkauf (KitchenOwl) | `kitchenowl` | 8082 | nach 1. Login **API-Token** erstellen |
| Dokumente (Paperless-ngx) | `paperless` | 8081 | Admin erzeugt der Installer; **API-Token** in der UI |
| Inventar (Homebox) | `homebox` | 7745 | nach 1. Login **API-Token** erstellen |
| KI (NousResearch/hermes-agent) | `agent` | 8642 | `hermes setup` (Codex/Nous) – der Installer stößt es an |

Die Auswahl landet als **`COMPOSE_PROFILES`** in der `.env`; Docker Compose liest
das automatisch, `docker compose up -d` startet genau diese Dienste mit.

## Ablauf (One-Shot)

```bash
./install.sh          # Ziel wählen (lokal/Docker), Dienste je i/v/Enter,
                      # dann: Deps, .env, Container, Admin, hermes-agent-Login
```

**Wichtig – API-Tokens:** Vikunja/KitchenOwl/Paperless/Homebox erzeugen ihren
API-Token erst **nach dem ersten Login** in ihrer Weboberfläche
(`http://<PUBLIC_HOST>:<port>`). Danach:

1. Token in der jeweiligen Web-UI erstellen.
2. In die `.env` eintragen (`VIKUNJA_TOKEN`, `KITCHENOWL_TOKEN`,
   `PAPERLESS_TOKEN`, `HOMEBOX_TOKEN`).
3. `docker compose restart hermes` (bzw. `systemctl restart hermes` bei lokaler
   Installation).

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
