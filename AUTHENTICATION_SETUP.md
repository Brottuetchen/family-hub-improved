# Family Hub - Authentication Setup Guide

## Sicheres Login-System mit JWT-Authentifizierung

Diese Anleitung erklärt, wie du das neue Authentifizierungssystem für deinen Family Hub einrichtest.

---

## 🔐 Sicherheitsfeatures

- **JWT-basierte Authentifizierung** mit Access- und Refresh-Tokens
- **bcrypt-gehashte Passwörter** (niemals im Klartext gespeichert)
- **HttpOnly-Cookies** für Token-Speicherung (Schutz vor XSS)
- **Rate Limiting** gegen Brute-Force-Angriffe (5 Versuche pro 15 Minuten)
- **Session Management** mit Token-Rotation
- **Automatische Token-Refresh** (alle 25 Minuten)
- **SQLite-Datenbank** für Benutzerverwaltung
- **Admin-Rollen** für geschützte Endpoints

---

## 📋 Voraussetzungen

- Python 3.8+
- Bestehende Family Hub Installation
- HTTPS-fähiger Webserver (empfohlen für Produktion)

---

## 🚀 Installation

### Schritt 1: Dependencies installieren

```bash
cd backend
pip install -r requirements.txt
```

Die neuen Dependencies umfassen:
- `python-jose` - JWT Token Handling
- `passlib[bcrypt]` - Passwort Hashing
- `bcrypt` - Kryptographie
- `sqlalchemy` - Datenbank ORM
- `slowapi` - Rate Limiting

### Schritt 2: Umgebungsvariablen setzen (optional)

Erstelle eine `.env`-Datei im `backend`-Verzeichnis:

```env
# Wichtig: Ändere diesen Secret Key!
SECRET_KEY=dein-super-sicherer-secret-key-hier

# Optional: Datenbank-URL (Standard: SQLite)
DATABASE_URL=sqlite:///./family_hub.db

# Optional: Token-Ablaufzeiten
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

**WICHTIG:** Generiere einen sicheren Secret Key:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Schritt 3: Datenbank initialisieren

Die Datenbank wird automatisch beim ersten Start des Backends initialisiert.

Starte den Backend-Server:
```bash
cd backend
python main.py
```

Du solltest folgende Meldung sehen:
```
Database initialized
IMPORTANT: Create admin user with: python create_admin.py
```

### Schritt 4: Admin-Benutzer erstellen

Erstelle deinen ersten Admin-Benutzer:

```bash
cd backend
python create_admin.py
```

Das interaktive Script fragt dich nach:
- **Username** (z.B. `admin`)
- **Email** (z.B. `family@example.com`)
- **Full Name** (optional)
- **Password** (mindestens 8 Zeichen)

Beispiel:
```
Family Hub - Admin User Creation
==================================================

Please provide admin user details:

Username: admin
Email: family@example.com
Full Name (optional): Family Admin
Password: ********
Confirm Password: ********

Creating admin user...

==================================================
✓ Admin user created successfully!
==================================================

Username: admin
Email: family@example.com
Full Name: Family Admin
Admin: Yes

You can now log in with these credentials.
```

---

## 🌐 Konfiguration für öffentlichen Zugriff

### Option 1: Nginx Reverse Proxy (empfohlen)

Wenn du bereits **Nginx Proxy Manager** (192.168.188.4) nutzt, erstelle einen neuen Proxy Host:

1. **Domain/Subdomain:** `familyhub.deinedomain.de`
2. **Scheme:** `http`
3. **Forward Hostname/IP:** IP deines Family Hub Containers
4. **Forward Port:** `8000`
5. **SSL:** Aktiviere SSL/TLS mit Let's Encrypt
6. **Websockets Support:** Aktivieren

**Wichtig:** Stelle sicher, dass HTTPS aktiviert ist, damit die HttpOnly-Cookies funktionieren!

### Option 2: Cloudflare Tunnel

Für sichere Verbindungen ohne Port-Forwarding:

```bash
cloudflared tunnel --url http://localhost:8000
```

### Option 3: Tailscale (VPN)

Für privaten Zugriff innerhalb deines Netzwerks:
```bash
tailscale up
```

---

## 🔒 Geschützte Endpoints

Nach der Authentifizierung sind folgende Endpoints geschützt:

### Admin-Endpoints (nur für Admin-Benutzer)
- `POST /api/push/admin/send` - Push-Benachrichtigungen senden
- `GET /api/push/subscriptions` - Push-Subscriptions verwalten
- `DELETE /api/push/subscriptions/{id}` - Subscription löschen
- `POST /api/auth/users` - Neue Benutzer erstellen
- `GET /api/auth/users` - Alle Benutzer anzeigen
- `DELETE /api/auth/users/{id}` - Benutzer löschen

### Öffentliche Endpoints (keine Authentifizierung erforderlich)
- `GET /api/health` - Health Check
- `GET /api/vapid-public-key` - VAPID Key für Push
- `POST /api/push/subscribe` - Push-Subscription registrieren
- `GET /api/services/status` - Service Status
- `GET /api/plex/stats` - Plex Statistiken
- Alle statischen Dateien (Frontend)

---

## 👥 Benutzerverwaltung

### Weitere Benutzer hinzufügen (als Admin)

```bash
curl -X POST "https://your-domain.com/api/auth/users" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "neuer_user",
    "email": "user@example.com",
    "password": "sicheres_passwort",
    "full_name": "Neuer Benutzer",
    "is_admin": false
  }'
```

### Passwort ändern

Benutzer können ihr Passwort über den `/api/auth/change-password` Endpoint ändern:

```bash
curl -X POST "https://your-domain.com/api/auth/change-password" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "current_password": "altes_passwort",
    "new_password": "neues_passwort"
  }'
```

---

## 🧪 Testen der Authentifizierung

### 1. Login testen

Öffne `https://your-domain.com/login.html` im Browser:
- Gib Username und Passwort ein
- Bei erfolgreicher Authentifizierung wirst du zu `/index.html` weitergeleitet

### 2. API direkt testen

```bash
# Login
curl -X POST "http://localhost:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "dein_passwort"}' \
  -c cookies.txt

# Geschützte Route aufrufen
curl -X GET "http://localhost:8000/api/auth/me" \
  -b cookies.txt

# Logout
curl -X POST "http://localhost:8000/api/auth/logout" \
  -b cookies.txt
```

---

## 🛡️ Sicherheits-Best-Practices

### Für Produktion

1. **HTTPS erzwingen**
   - Setze `secure=True` für Cookies (bereits implementiert)
   - Verwende einen Reverse Proxy mit SSL/TLS

2. **Starker Secret Key**
   ```bash
   # Generiere einen sicheren 32-Byte Key
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Firewall-Regeln**
   - Erlaube nur HTTPS-Traffic (Port 443)
   - Blockiere direkten Zugriff auf Port 8000

4. **Rate Limiting**
   - Bereits implementiert: 5 Login-Versuche pro 15 Minuten
   - Bei Bedarf anpassen in `auth.py`

5. **Regelmäßige Updates**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

### Backup der Datenbank

Die Benutzerdatenbank liegt unter `backend/family_hub.db`. Sichere diese Datei regelmäßig:

```bash
# Backup erstellen
cp backend/family_hub.db backend/family_hub.db.backup

# Oder automatisch per Cron (täglich um 2 Uhr)
0 2 * * * cp /path/to/backend/family_hub.db /path/to/backups/family_hub_$(date +\%Y\%m\%d).db
```

---

## 🐛 Troubleshooting

### Problem: "Database locked" Fehler

**Lösung:** SQLite kann Probleme mit gleichzeitigen Schreibzugriffen haben. Verwende PostgreSQL für höhere Last:

```bash
pip install psycopg2-binary
export DATABASE_URL="postgresql://user:password@localhost/familyhub"
```

### Problem: Cookies werden nicht gesetzt

**Ursache:** HTTPS ist nicht aktiviert, aber `secure=True` ist gesetzt.

**Lösung:**
- Aktiviere HTTPS im Reverse Proxy
- ODER für lokale Tests: Ändere `secure=True` zu `secure=False` in `auth.py`

### Problem: "Too many login attempts"

**Ursache:** Rate Limiting aktiv nach 5 fehlgeschlagenen Versuchen.

**Lösung:**
- Warte 15 Minuten
- ODER lösche Einträge in `login_attempts` Tabelle

```bash
sqlite3 backend/family_hub.db "DELETE FROM login_attempts WHERE username='admin';"
```

### Problem: Token läuft ab

**Ursache:** Access Token ist nach 30 Minuten abgelaufen.

**Lösung:** Der Browser sollte automatisch den Refresh-Token verwenden. Falls nicht, melde dich neu an.

---

## 📊 Datenbankstruktur

### Tabellen

**users**
- `id` - Primärschlüssel
- `username` - Eindeutiger Benutzername
- `email` - Eindeutige E-Mail
- `hashed_password` - bcrypt-Hash
- `full_name` - Vollständiger Name (optional)
- `is_active` - Benutzer aktiv?
- `is_admin` - Admin-Rechte?
- `created_at` - Erstellungsdatum
- `updated_at` - Letzte Änderung
- `last_login` - Letzter Login

**refresh_tokens**
- `id` - Primärschlüssel
- `user_id` - Referenz zu User
- `token` - Refresh Token (unique)
- `expires_at` - Ablaufdatum
- `revoked` - Wurde widerrufen?
- `user_agent` - Browser/Client Info
- `ip_address` - IP-Adresse

**login_attempts**
- `id` - Primärschlüssel
- `username` - Versuchter Username
- `ip_address` - IP-Adresse
- `success` - Erfolgreich?
- `attempted_at` - Zeitpunkt

---

## 🎯 Nächste Schritte

Nach erfolgreicher Installation:

1. ✅ Erstelle Admin-Benutzer
2. ✅ Teste Login über `/login.html`
3. ✅ Richte HTTPS ein (Nginx Proxy Manager)
4. ✅ Füge weitere Familienmitglieder hinzu
5. ✅ Konfiguriere automatisches Backup
6. ✅ Überwache Login-Versuche in `login_attempts` Tabelle

---

## 📞 Support

Bei Problemen:
1. Prüfe die Logs: `tail -f backend/logs/app.log`
2. Teste die API Health: `curl http://localhost:8000/api/health`
3. Prüfe die Auth Health: `curl http://localhost:8000/api/auth/health`

---

**Viel Erfolg mit dem sicheren Family Hub! 🏠🔒**
