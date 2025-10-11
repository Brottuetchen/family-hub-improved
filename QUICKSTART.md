# Family Hub - Quick Start Guide

**Von 0 auf deployed in 15 Minuten** ⚡

---

## Schritt 1: VAPID Keys generieren (2 Minuten)

```bash
# Auf deinem lokalen PC oder in einem LXC
pip install pywebpush

# Keys generieren
python3 << 'EOF'
from pywebpush import WebPusher
keys = WebPusher.create_keys()
print("\n" + "="*50)
print("VAPID KEYS - Speichere diese sicher!")
print("="*50)
print(f"PRIVATE KEY:\n{keys['private_key'].decode()}\n")
print(f"PUBLIC KEY:\n{keys['public_key'].decode()}")
print("="*50 + "\n")
EOF
```

**Speichere die Ausgabe!** Du brauchst sie im nächsten Schritt.

---

## Schritt 2: Projekt in LXC deployen (5 Minuten)

### Option A: Automatisches Deployment (empfohlen)

```bash
# Auf deinem Proxmox Host
cd /tmp
git clone https://github.com/yourusername/family-hub.git
cd family-hub
chmod +x deploy.sh

# Deployment starten
./deploy.sh

# Folge den Anweisungen im Script
```

### Option B: Manuelles Deployment

```bash
# 1. LXC erstellen (falls noch nicht vorhanden)
pct create 145 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname familyhub \
  --memory 2048 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.188.145/24,gw=192.168.188.1 \
  --storage local-lvm \
  --rootfs local-lvm:8

pct start 145

# 2. In Container einloggen
pct enter 145

# 3. Dependencies installieren
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git

# 4. Family Hub klonen
cd /opt
git clone https://github.com/yourusername/family-hub.git
cd family-hub/backend

# 5. Python Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 6. .env konfigurieren
cp .env.example .env
nano .env
# Trage deine VAPID Keys ein (aus Schritt 1)

# 7. Systemd Service
nano /etc/systemd/system/familyhub.service
```

**familyhub.service Inhalt:**

```ini
[Unit]
Description=Family Hub FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/family-hub/backend
Environment="PATH=/opt/family-hub/backend/venv/bin"
ExecStart=/opt/family-hub/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Service aktivieren
systemctl daemon-reload
systemctl enable familyhub.service
systemctl start familyhub.service
systemctl status familyhub.service
```

---

## Schritt 3: VAPID Keys eintragen (3 Minuten)

```bash
# Im LXC Container
nano /opt/family-hub/backend/main.py

# Suche nach diesen Zeilen und ersetze die Keys:
VAPID_PRIVATE_KEY = "YOUR_VAPID_PRIVATE_KEY_HERE"  # <- Aus Schritt 1
VAPID_PUBLIC_KEY = "YOUR_VAPID_PUBLIC_KEY_HERE"    # <- Aus Schritt 1

# Speichern: Ctrl+O, Enter, Ctrl+X

# Service neu starten
systemctl restart familyhub.service
```

---

## Schritt 4: PNG Icons generieren (2 Minuten)

**Online-Methode (einfachste):**

1. Öffne https://cloudconvert.com/svg-to-png
2. Upload `public/assets/icons/app-icon.svg`
3. Setze Größe auf 192x192 → Konvertieren → Download
4. Wiederholen mit 512x512
5. Speichere als:
   - `app-icon-192.png`
   - `app-icon-512.png`
6. Kopiere in Container:

```bash
# Von deinem PC aus
scp app-icon-*.png root@192.168.188.145:/opt/family-hub/public/assets/icons/
```

**Alternativ mit ImageMagick (im Container):**

```bash
apt install imagemagick
cd /opt/family-hub/public/assets/icons
convert -background none -resize 192x192 app-icon.svg app-icon-192.png
convert -background none -resize 512x512 app-icon.svg app-icon-512.png
```

---

## Schritt 5: Testen (3 Minuten)

### 1. Backend-Test

```bash
# Check Service
systemctl status familyhub.service

# Test API
curl http://localhost:8000
# Sollte JSON mit "status": "online" zurückgeben

curl http://localhost:8000/api/vapid-public-key
# Sollte deinen Public Key zeigen
```

### 2. Frontend-Test

Öffne im Browser: **http://192.168.188.145:8000**

Du solltest sehen:
- ✅ Sticky Header mit Navigation
- ✅ Quick Stats Cards (Plex, Overseerr, System)
- ✅ Services Grid mit allen Services
- ✅ Newsletter-Section

### 3. Push Notifications Test

1. Klicke auf die Glocke 🔔 im Header
2. Klicke "Aktivieren"
3. Browser fragt nach Berechtigung → **"Erlauben"**
4. Glocke sollte grün werden ✅

**Test-Notification senden:**

```bash
# Im Container oder via curl
curl -X POST http://localhost:8000/api/push/notify \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Notification",
    "body": "Family Hub funktioniert!",
    "url": "/"
  }'
```

Du solltest eine Desktop-Notification sehen! 🎉

### 4. In-App Browser Test

1. Klicke auf einen Service (z.B. "Plex Media Server")
2. Service sollte im In-App Browser öffnen (nicht neuer Tab)
3. "Zurück" Button funktioniert

---

## Schritt 6: Nginx Reverse Proxy (Optional, 3 Minuten)

Wenn du bereits Nginx Proxy Manager hast:

1. Öffne NPM: http://192.168.188.4:81
2. Proxy Hosts → Add Proxy Host
3. Details:
   - **Domain Names**: `family.t-acc.com` (oder deine Domain)
   - **Scheme**: `http`
   - **Forward Hostname**: `192.168.188.145`
   - **Forward Port**: `8000`
   - **Cache Assets**: ✅
   - **Block Common Exploits**: ✅
4. SSL Tab:
   - **SSL Certificate**: Request new SSL (Let's Encrypt)
   - **Force SSL**: ✅
   - **HTTP/2**: ✅
5. Save

Jetzt erreichbar unter: **https://family.t-acc.com** 🎉

---

## Fertig! 🎊

Du hast jetzt:
- ✅ Family Hub PWA deployed
- ✅ Push Notifications aktiviert
- ✅ In-App Service Browser
- ✅ Quick Stats Dashboard
- ✅ Newsletter-Integration
- ✅ Dark Mode Support
- ✅ Offline-Fähigkeit

---

## Troubleshooting

### Backend startet nicht

```bash
# Logs anzeigen
journalctl -u familyhub.service -f

# Manuell testen
cd /opt/family-hub/backend
source venv/bin/activate
python main.py
# Fehler sollten jetzt sichtbar sein
```

**Häufige Fehler:**

1. **"ModuleNotFoundError: No module named 'fastapi'"**
   → `pip install -r requirements.txt` vergessen

2. **"Port 8000 already in use"**
   → Anderer Service läuft auf Port 8000
   → Ändere Port in `main.py` und `systemd service`

3. **"VAPID keys not configured"**
   → Keys in `main.py` eintragen (Schritt 3)

### Push Notifications funktionieren nicht

1. **Browser-Konsole prüfen (F12)**
   → Zeigt API-Fehler an

2. **Backend-API testen:**
   ```bash
   curl http://192.168.188.145:8000/api/vapid-public-key
   ```
   → Sollte Public Key zeigen, nicht "YOUR_VAPID_PUBLIC_KEY_HERE"

3. **HTTPS erforderlich (außer localhost)**
   → Auf `family.t-acc.com` mit SSL umstellen
   → Oder: In `app.js` auf localhost testen

4. **iOS Safari:**
   → Benötigt iOS 16.4+
   → App muss zu Home-Screen hinzugefügt werden
   → Dann funktionieren Push Notifications

### Services laden nicht (In-App Browser)

Manche Services blockieren iframe-Einbettung.

**Lösung 1: X-Frame-Options Header ändern**

Wenn du Nginx benutzt, füge hinzu:

```nginx
proxy_hide_header X-Frame-Options;
proxy_set_header X-Frame-Options "SAMEORIGIN";
```

**Lösung 2: Direktlink-Button**

Füge in `service-viewer.html` einen "In neuem Tab öffnen" Button hinzu.

---

## Next Steps

1. **Newsletter erstellen:**
   - Editiere `public/newsletters/index.json`
   - Füge HTML-Newsletter in `public/newsletters/` hinzu

2. **Mehr Services hinzufügen:**
   - Editiere `public/data/services.json`
   - Erstelle Icons in `public/assets/icons/`

3. **Automatische Updates:**
   - Setup Cron Job für neue Plex-Inhalte
   - Push Notification bei neuem Content

4. **Multi-User:**
   - Implementiere User-Login
   - Personalisierte Benachrichtigungen

---

**Brauchst du Hilfe?**

- Email: trapp.constantin@gmail.com
- GitHub: [Dein Repo]
- Homelab Docs: http://192.168.188.62:8080

**Viel Erfolg!** 🚀
