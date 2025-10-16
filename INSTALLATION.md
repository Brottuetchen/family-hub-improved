# Family Hub - Schnellstart Installation

## 🚀 Schnellinstallation (5 Minuten)

### 1. Dependencies installieren

```bash
cd backend
pip install -r requirements.txt
```

### 2. Backend starten

```bash
python main.py
```

Der Server läuft jetzt auf `http://localhost:8000`

### 3. Admin-Benutzer erstellen

In einem neuen Terminal:

```bash
cd backend
python create_admin.py
```

Gib deine Daten ein:
```
Username: admin
Email: deine@email.de
Full Name: Admin
Password: ******** (mindestens 8 Zeichen)
Confirm Password: ********
```

### 4. Login testen

Öffne im Browser:
```
http://localhost:8000/login.html
```

Melde dich mit deinen Credentials an!

---

## 📦 Was wurde installiert?

### Neue Dateien

**Backend:**
- `backend/database.py` - Datenbankmodelle
- `backend/auth.py` - Authentifizierungslogik
- `backend/auth_router.py` - Auth-Endpoints
- `backend/create_admin.py` - Admin-Setup-Script
- `backend/family_hub.db` - SQLite-Datenbank (nach erstem Start)

**Frontend:**
- `public/login.html` - Login-Seite
- `public/login.js` - Login-Logik
- `public/auth-utils.js` - Auth-Utility-Modul

**Dokumentation:**
- `AUTHENTICATION_SETUP.md` - Vollständige Setup-Anleitung
- `INSTALLATION.md` - Diese Datei

### Aktualisierte Dateien

- `backend/requirements.txt` - Neue Dependencies
- `backend/main.py` - Auth-Integration
- `public/index.html` - Logout-Button
- `public/app.js` - Auth-Checks

---

## 🔐 Sicherheitsfeatures

✅ **JWT-Tokens** - Access & Refresh Tokens
✅ **bcrypt Hashing** - Passwörter sicher gespeichert
✅ **HttpOnly Cookies** - XSS-Schutz
✅ **Rate Limiting** - 5 Versuche pro 15 Min
✅ **Session Management** - Automatischer Token-Refresh
✅ **Admin-Rollen** - Geschützte Endpoints

---

## 🌐 Für Internet-Zugriff einrichten

### Mit Nginx Proxy Manager (empfohlen)

1. Öffne Nginx Proxy Manager: `http://192.168.188.4`
2. Erstelle neuen Proxy Host:
   - **Domain:** `familyhub.deinedomain.de`
   - **Forward to:** `<family-hub-ip>:8000`
   - **SSL:** Let's Encrypt aktivieren
3. Fertig! Zugriff über HTTPS

### Mit Cloudflare Tunnel

```bash
cloudflared tunnel --url http://localhost:8000
```

---

## 👥 Weitere Benutzer hinzufügen

Als Admin einloggen, dann:

```bash
curl -X POST "http://localhost:8000/api/auth/users" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "maria",
    "email": "maria@familie.de",
    "password": "sicheres_passwort",
    "full_name": "Maria Müller",
    "is_admin": false
  }'
```

---

## 🐛 Probleme?

### Backend startet nicht
```bash
# Dependencies neu installieren
pip install --upgrade -r requirements.txt
```

### Kann keinen Admin erstellen
```bash
# Datenbank zurücksetzen (ACHTUNG: Löscht alle Benutzer!)
rm backend/family_hub.db
python backend/create_admin.py
```

### Login funktioniert nicht
- Prüfe ob Backend läuft: `http://localhost:8000/api/health`
- Prüfe Auth-Status: `http://localhost:8000/api/auth/health`
- Browser-Console öffnen (F12) für Fehlermeldungen

---

## 📖 Vollständige Dokumentation

Siehe [AUTHENTICATION_SETUP.md](AUTHENTICATION_SETUP.md) für:
- Erweiterte Konfiguration
- Sicherheits-Best-Practices
- Troubleshooting
- API-Dokumentation
- Datenbank-Details

---

## ✅ Checkliste

- [ ] Dependencies installiert
- [ ] Backend gestartet
- [ ] Admin-Benutzer erstellt
- [ ] Login getestet
- [ ] HTTPS eingerichtet (für Produktion)
- [ ] Weitere Benutzer hinzugefügt
- [ ] Backup konfiguriert

---

**Viel Spaß mit dem sicheren Family Hub! 🏠🔒**
