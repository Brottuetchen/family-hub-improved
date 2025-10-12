# Family Hub PWA v2.0

**Zentrale Familien-App für Media Services, Newsletter und Homelab-Verwaltung**

Eine moderne Progressive Web App (PWA) mit FastAPI-Backend, Push Notifications und In-App Service-Browser.

---

## Aktueller Projektstatus

- ✅ **Live-Betrieb:** Die Anwendung ist im LXC-Container (`192.168.188.150:8000`) deployt und aktiv.
- ✅ **Push Notifications:** VAPID Keys sind konfiguriert, Push-Benachrichtigungen sind voll funktionsfähig.
- ✅ **Newsletter-Automatisierung:** Der n8n-Workflow triggert wöchentlich das Newsletter-Skript und sendet Benachrichtigungen.
- ✅ **PWA-Ready:** Alle notwendigen Assets, inklusive PNG-Icons, sind vorhanden und die App ist installierbar.

Dieser Stand entspricht dem aktuellen Handoff für Codex: Funktionalität ist vorhanden, Deployment (LXC + VAPID + Icons) steht noch aus.


---

## Features

### Frontend Features
- **Moderner Sticky Header** mit Navigation und Notification-Bell
- **Quick Stats Dashboard** mit Live-Updates von Plex, Overseerr und System-Status
- **In-App Service Browser** - Alle Services öffnen sich innerhalb der App (kein neuer Tab)
- **Dark Mode Support** - Automatische Erkennung der System-Einstellung
- **Push Notifications** - Web Push für Newsletter und System-Updates
- **PWA Features** - Installierbar auf iOS, Android, Desktop
- **Offline Support** - Service Worker mit intelligenter Cache-Strategie
- **Newsletter-Integration** - Kuratierte Film- und Serien-Empfehlungen

### Backend Features (FastAPI)
- **REST API** für Stats, Service-Status und Push Notifications
- **Plex Integration** - Live-Streams, Recently Added
- **Overseerr Integration** - Pending Requests
- **Push Notification Server** - Web Push mit VAPID
- **Service Health Checks** - Automatisches Monitoring aller Homelab-Services

### Services
- Plex Media Server
- Overseerr (Media Requests)
- Sonarr, Radarr, Lidarr (Automation)
- SABnzbd (Usenet Downloader)
- Trilium Notes
- Immich (Foto-Backup)
- Audiobookshelf
- Nextcloud
- n8n Workflows
- Grafana Monitoring

---

## Projektstruktur

```
family-hub-improved/
├── public/                      # Frontend (PWA)
│   ├── index.html              # Haupt-HTML mit neuem Header
│   ├── app.js                  # Main JS mit Stats & Push Manager
│   ├── styles.css              # Umfassendes CSS mit Dark Mode
│   ├── service-viewer.html     # In-App Browser für Services
│   ├── service-viewer.js       # Service Viewer Logic
│   ├── push-manager.js         # Push Notification Manager
│   ├── service-worker.js       # Enhanced SW mit Push Support
│   ├── manifest.webmanifest    # PWA Manifest
│   ├── assets/
│   │   └── icons/              # SVG Icons (app-icon, services)
│   ├── data/
│   │   └── services.json       # Service-Konfiguration mit Plex
│   └── newsletters/
│       └── index.json          # Newsletter-Archiv
├── backend/                     # FastAPI Backend
│   ├── main.py                 # FastAPI App mit allen Endpoints
│   └── requirements.txt        # Python Dependencies
└── README.md                   # Diese Datei
```

---

## Installation & Setup

### Voraussetzungen
- Python 3.9+ (für Backend)
- Node.js/npm (optional, für lokales Testing)
- Proxmox LXC Container (für Production)

### 1. Repository Klonen

```bash
cd /opt
git clone https://github.com/yourusername/family-hub.git
cd family-hub
```

### 2. Backend Setup

```bash
cd backend

# Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# oder: venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# VAPID Keys generieren (für Push Notifications)
python -c "from pywebpush import WebPusher; print(WebPusher.create_keys())"

# Keys in main.py eintragen (siehe Konfiguration)
```

### 3. Konfiguration

Editiere `backend/main.py` und trage deine Keys ein:

```python
# VAPID Keys (aus Schritt 2)
VAPID_PRIVATE_KEY = "YOUR_GENERATED_PRIVATE_KEY"
VAPID_PUBLIC_KEY = "YOUR_GENERATED_PUBLIC_KEY"

# Service URLs (falls abweichend)
PLEX_URL = "http://192.168.188.7:32400"
PLEX_TOKEN = "YOUR_PLEX_TOKEN"
OVERSEERR_URL = "http://192.168.188.79:5055"
OVERSEERR_API_KEY = "YOUR_OVERSEERR_KEY"
```

### 4. Frontend Konfiguration

Editiere `public/app.js` und passe die API-URL an:

```javascript
const API_BASE_URL = 'http://192.168.188.143:8000'; // Deine Backend-URL
const USE_MOCK_DATA = false; // Auf false wenn Backend läuft
```

### 5. Development Server starten

```bash
# Backend starten (Terminal 1)
cd backend
python main.py
# Backend läuft auf: http://0.0.0.0:8000

# Frontend wird vom Backend ausgeliefert
# Öffne: http://localhost:8000
```

---

## Deployment auf Proxmox LXC

### Option 1: Bestehendes Homepage-LXC erweitern (CT 119)

```bash
# SSH in Homepage Container
pct enter 119

# Familie Hub installieren
cd /opt
git clone <dein-repo> family-hub
cd family-hub/backend

# Python Packages installieren
pip install -r requirements.txt

# Systemd Service erstellen
nano /etc/systemd/system/familyhub.service
```

**Systemd Service:**

```ini
[Unit]
Description=Family Hub FastAPI Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/family-hub/backend
Environment="PATH=/opt/family-hub/backend/venv/bin"
ExecStart=/opt/family-hub/backend/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# Service aktivieren und starten
systemctl enable familyhub.service
systemctl start familyhub.service
systemctl status familyhub.service
```

### Option 2: Neues LXC erstellen

```bash
# Auf Proxmox Host
pct create 145 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
  --hostname familyhub \
  --memory 2048 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.188.145/24,gw=192.168.188.1 \
  --storage local-lvm \
  --rootfs local-lvm:8

# Container starten
pct start 145

# Container betreten
pct enter 145

# System aktualisieren
apt update && apt upgrade -y

# Python und Git installieren
apt install -y python3 python3-pip python3-venv git

# Family Hub installieren (siehe Option 1)
```

### Nginx Reverse Proxy (optional)

Wenn du bereits Nginx Proxy Manager (CT 101) verwendest:

1. Öffne Nginx Proxy Manager: http://192.168.188.4:81
2. Erstelle neuen Proxy Host:
   - Domain: `family.t-acc.com`
   - Forward Hostname/IP: `192.168.188.145` (oder 119)
   - Forward Port: `8000`
   - SSL: Let's Encrypt aktivieren

---

## PNG Icons erstellen

Die SVG Icons müssen noch in PNG konvertiert werden für PWA-Support:

```bash
# Mit Inkscape (Linux)
inkscape assets/icons/app-icon.svg --export-png=assets/icons/app-icon-192.png -w 192 -h 192
inkscape assets/icons/app-icon.svg --export-png=assets/icons/app-icon-512.png -w 512 -h 512

# Mit ImageMagick
convert -background none -resize 192x192 assets/icons/app-icon.svg assets/icons/app-icon-192.png
convert -background none -resize 512x512 assets/icons/app-icon.svg assets/icons/app-icon-512.png

# Online-Tool (einfachste Methode)
# Öffne https://cloudconvert.com/svg-to-png
# Upload app-icon.svg und konvertiere zu 192x192 und 512x512
```

---

## Push Notifications aktivieren

### 1. VAPID Keys generieren

```bash
# Python-Script für VAPID-Generierung
python3 << 'EOF'
from pywebpush import WebPusher
keys = WebPusher.create_keys()
print("Private Key:", keys['private_key'].decode())
print("Public Key:", keys['public_key'].decode())
EOF
```

### 2. Keys in Backend eintragen

```python
# backend/main.py
VAPID_PRIVATE_KEY = "ausgabe_von_oben_private_key"
VAPID_PUBLIC_KEY = "ausgabe_von_oben_public_key"
```

### 3. Backend neu starten

```bash
systemctl restart familyhub.service
```

### 4. Im Frontend testen

1. Öffne App: http://192.168.188.145:8000
2. Klicke auf Notification-Bell (Glocke) im Header
3. Klicke "Aktivieren"
4. Browser fragt nach Berechtigung → "Erlauben"
5. Test-Notification wird angezeigt

---

## API Endpoints

### Health Check
```
GET /
Antwort: {"status": "online", "version": "2.0.0", ...}
```

### VAPID Public Key
```
GET /api/vapid-public-key
Antwort: {"publicKey": "..."}
```

### Push Subscription
```
POST /api/push/subscribe
Body: {
  "endpoint": "...",
  "keys": {
    "auth": "...",
    "p256dh": "..."
  }
}
```

### Push Notification senden
```
POST /api/push/notify
Body: {
  "title": "Test",
  "body": "Nachricht",
  "url": "/",
  "icon": "/assets/icons/app-icon-192.png"
}
```

### Plex Stats
```
GET /api/plex/stats
Antwort: {
  "active_streams": 2,
  "streams": [...],
  "recently_added": [...]
}
```

### Overseerr Stats
```
GET /api/overseerr/stats
Antwort: {
  "pending_requests": 3,
  "recent_requests": [...]
}
```

### Service Status
```
GET /api/services/status
Antwort: [
  {"name": "Plex", "status": "online", "category": "media"},
  ...
]
```

---

## Troubleshooting

### Backend startet nicht

```bash
# Logs prüfen
journalctl -u familyhub.service -f

# Port bereits belegt?
netstat -tulpn | grep 8000

# Python-Fehler?
cd /opt/family-hub/backend
source venv/bin/activate
python main.py
```

### Push Notifications funktionieren nicht

1. Prüfe VAPID Keys in `main.py`
2. Prüfe Browser-Konsole (F12)
3. Teste API direkt:
   ```bash
   curl http://localhost:8000/api/vapid-public-key
   ```
4. Safari/iOS: Benötigt iOS 16.4+ und "Add to Home Screen"

### Services im In-App Browser laden nicht

- Manche Services blockieren iframe-Einbettung (X-Frame-Options)
- Lösung: Öffne in neuem Tab (Button in service-viewer.html ergänzen)

### Dark Mode funktioniert nicht

- Prüfe System-Einstellung: Windows/macOS Dark Mode aktiviert?
- Force Dark Mode in CSS:
  ```css
  :root { color-scheme: dark; }
  ```

---

## Next Steps / Roadmap

### Kurzfristig (v2.1)
- [ ] PNG Icons generieren (192x192, 512x512)
- [ ] Screenshots für PWA Manifest erstellen
- [ ] Newsletter-Generator Script schreiben
- [ ] SQLite Datenbank für Push Subscriptions
- [ ] Auto-Update Check (neue Plex-Inhalte)

### Mittelfristig (v2.5)
- [ ] User Authentication (Login-System)
- [ ] Multi-User Support (verschiedene Benachrichtigungen)
- [ ] Widget-System (Dashboard anpassbar)
- [ ] Kalender-Integration (Nextcloud)
- [ ] Grafana-Dashboards einbetten

### Langfristig (v3.0)
- [ ] Mobile Apps (React Native / Flutter)
- [ ] Voice Commands (Alexa/Google Home)
- [ ] Homelab-Automation (Container starten/stoppen)
- [ ] Media-Empfehlungen mit AI (GPT-Integration)

---

## Mitwirken

Pull Requests sind willkommen! Für größere Änderungen bitte zuerst ein Issue öffnen.

---

## Lizenz

MIT License - siehe LICENSE Datei

---

## Credits

- **Entwickelt von**: Constantin Trapp
- **Homelab**: Proxmox VE 8.x
- **Icons**: Custom SVG Icons
- **Inspiration**: Homepage Dashboard, Heimdall

---

## Support

Bei Fragen oder Problemen:
- Email: trapp.constantin@gmail.com
- GitHub Issues: [Link zu deinem Repo]
- Homelab-Dokumentation: Trilium Notes (http://192.168.188.62:8080)

---

**Viel Spaß mit deinem Family Hub!** 🏠🎬
