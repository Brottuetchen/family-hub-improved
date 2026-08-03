# Deployment

## Installer (empfohlen)

Der geführte Installer fragt alle URLs/IPs, API-Keys und Zugangsdaten ab,
erzeugt `SECRET_KEY` + VAPID-Schlüssel und schreibt die `.env`:

```bash
./install.sh                         # optional inkl. Docker-Start + Admin
# oder nur der Assistent:
python3 backend/scripts/setup.py
```

## Docker Compose (manuell)

```bash
cp .env.example .env
```

In `.env` mindestens setzen:
- `SECRET_KEY` – langer Zufallswert
  (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `POSTGRES_PASSWORD`
- `ENVIRONMENT=production`, `SECURE_COOKIES=true` (bei HTTPS)
- gewünschte Connector-URLs/Tokens

```bash
docker compose up -d --build
docker compose exec hermes python -m scripts.create_admin
```

Der Stack enthält `hermes` (Backend + Frontend), `db` (PostgreSQL) und `redis`.
Die `DATABASE_URL`/`REDIS_URL` werden im Compose automatisch auf die Container gesetzt.

## Reverse Proxy (Traefik / Nginx Proxy Manager)

Hermes hört intern auf Port 8000. Beispiel-Weiterleitung:

```
family.example.com  →  hermes:8000   (Let's Encrypt / TLS am Proxy)
```

Hinter TLS-Proxy: `SECURE_COOKIES=true` und Domain in `CORS_ORIGINS` eintragen
(oder `*` für rein internen Betrieb).

## Push Notifications (VAPID)

```bash
cd backend && python -m scripts.generate_vapid
# Ausgabe in .env eintragen: VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY
```

iOS benötigt iOS 16.4+ und „Zum Home-Bildschirm hinzufügen".

## PostgreSQL vs. SQLite

- **SQLite** (Default): ideal für Entwicklung/kleine Setups. Keine Konfiguration.
- **PostgreSQL** (Produktion): `DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/db`.
  Im Compose bereits vorverdrahtet.

## Backups

Zu sichern:
- PostgreSQL-Volume `hermes_pgdata` (oder `backend/hermes.db` bei SQLite)
- `.env` (enthält Secrets – sicher aufbewahren, **nicht** ins Git)

## Update

```bash
git pull
docker compose up -d --build
```

Das Schema wird beim Start via `create_all` idempotent aktualisiert. Für
Breaking-Changes ist mittelfristig Alembic vorgesehen (siehe ROADMAP).

## Ohne Docker (systemd)

```ini
[Unit]
Description=Hermes Family OS
After=network.target

[Service]
WorkingDirectory=/opt/hermes/backend
Environment=PATH=/opt/hermes/backend/.venv/bin
EnvironmentFile=/opt/hermes/.env
ExecStart=/opt/hermes/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```
