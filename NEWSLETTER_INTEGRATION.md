# Newsletter + Family Hub Integration - Dokumentation

## Übersicht

Diese Integration verbindet den **Weekly Media Newsletter** mit der **Family Hub PWA** und ermöglicht:

1. ✅ Automatische Newsletter-Generierung (Freitag 12:00 Uhr)
2. ✅ JSON-Index für Family Hub Frontend
3. ✅ Push Notifications an alle Subscribers
4. ✅ n8n Workflow-Automation

---

## Was wurde geändert?

### 1. Newsletter-Script erweitert

**Datei:** `C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py`

#### Neue Funktionen:

**`extract_ai_reason(item: MediaItem) -> str`**
- Extrahiert AI-Empfehlung aus MediaItem
- Fallback auf Overview wenn keine AI-Reason vorhanden

**`generate_json_index(selected_movies, selected_shows, all_movies, all_shows, filepath) -> bool`**
- Erstellt/aktualisiert `newsletters/index.json`
- Speichert Newsletter-Metadaten für Family Hub
- Format:
  ```json
  [
    {
      "date": "2025-10-11",
      "title": "Weekly Media Newsletter - KW 41",
      "path": "weekly_newsletter_2025-10-11.html",
      "movies": [
        {"title": "Movie Title", "rating": 8.5, "reason": "AI Empfehlung..."},
        ...
      ],
      "shows": [
        {"title": "Show Title", "rating": 8.3, "reason": "AI Empfehlung..."},
        ...
      ]
    }
  ]
  ```
- Behält nur letzte 50 Newsletter

**`send_push_notification(newsletter_title: str) -> bool`**
- Sendet Push Notification an Family Hub Backend
- Payload: title, body, url
- Fehlertoleranz: Gibt Warnung aber stoppt nicht

#### Integration in main():

```python
# Nach save_report():
if success:
    # 1. JSON Index erstellen
    generate_json_index(...)

    # 2. Trilium updaten (existiert bereits)
    update_trilium_knowledge_base(...)

    # 3. Push Notification senden
    send_push_notification(...)
```

### 2. Family Hub Backend erweitert

**Datei:** `C:\Users\trapp\family-hub-improved\backend\main.py`

#### Änderungen:

**Endpoint: `/api/push/notify` (erweitert)**
- Akzeptiert jetzt `Dict` statt `PushNotification` Model
- Unterstützt `url` Parameter für Navigation
- Flexible Payload-Struktur

**Neuer Endpoint: `/api/newsletter/reload`**
- POST Request
- Lädt Newsletter Index aus `../public/newsletters/index.json`
- Sendet Push an alle Subscriber
- Response:
  ```json
  {
    "success": true,
    "newsletter": {...},
    "push_sent": 2,
    "push_failed": 0
  }
  ```

---

## Setup & Konfiguration

### Schritt 1: Verzeichnisse prüfen

```bash
# Prüfe NAS-Zugriff
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# Erstelle Verzeichnis falls nicht vorhanden
mkdir -p "\\192.168.188.6\Backups\Homelab\reports\newsletters"
```

### Schritt 2: Newsletter-Script testen

```bash
# Manueller Test
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# Checke Logs
cat "\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log"

# Checke Output
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"
```

**Erwartete Ausgabe:**
- `weekly_newsletter_2025-10-11.html` erstellt
- `index.json` erstellt/aktualisiert
- Log: "JSON index created successfully!"
- Log: "Push notification sent successfully!"

### Schritt 3: Family Hub Backend starten

```bash
cd C:\Users\trapp\family-hub-improved\backend
python main.py
```

**Erwartete Ausgabe:**
```
INFO:     Started server process
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Family Hub API started
```

### Schritt 4: Integration testen

```bash
cd C:\Users\trapp\family-hub-improved
python test_integration.py
```

**Erwartete Ausgabe:**
```
============================================================
FAMILY HUB INTEGRATION TEST
============================================================
🔍 Testing Family Hub API...
✅ Family Hub API is running

🔍 Testing Push Notification endpoint...
✅ Push endpoint works: {'success': 0, 'failed': 0, 'message': 'No subscribers'}

🔍 Testing NAS access...
✅ NAS accessible: \\192.168.188.6\Backups\Homelab\reports\newsletters
   Found 1 newsletter HTML files

🔍 Testing Newsletter Index...
✅ Newsletter Index found: 1 entries
   Latest: Weekly Media Newsletter - KW 41 (2025-10-11)
   Movies: 5
   Shows: 5

🔍 Testing Newsletter Reload endpoint...
✅ Newsletter reload works
   Push sent: 0
   Push failed: 0

============================================================
✅ ALL TESTS PASSED (5/5) - Integration ready!
============================================================
```

### Schritt 5: n8n Workflow importieren

1. Öffne n8n: http://192.168.188.131:5678
2. Klicke auf **"+ New Workflow"**
3. Klicke auf **"..." → "Import from File"**
4. Wähle: `C:\Users\trapp\family-hub-improved\n8n\weekly_newsletter_workflow.json`
5. **Workflow prüfen:**
   - Schedule: Freitag 12:00 (`0 12 * * 5`)
   - Execute Command: Python-Pfad korrekt?
   - HTTP Request: IP `192.168.188.150:8000` korrekt?
6. **Manueller Test:**
   - Klicke "Execute Workflow" (Play-Button oben rechts)
   - Prüfe Logs in jedem Node
7. **Aktivieren:**
   - Toggle "Active" oben rechts auf ON
   - Workflow läuft jetzt automatisch jeden Freitag um 12:00 Uhr

---

## Workflow-Ablauf

```
┌─────────────────────────┐
│ Schedule Trigger        │
│ (Freitag 12:00)         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Execute Newsletter      │
│ Script (Python)         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ IF Success?             │
│ (Exit Code = 0)         │
└─────┬─────────────┬─────┘
      │             │
   Yes│             │No
      │             ▼
      │      ┌──────────────┐
      │      │ Log Error    │
      │      └──────────────┘
      │
      ▼
┌─────────────────────────┐
│ Send Push Notification  │
│ (POST to Family Hub)    │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Log Success             │
└─────────────────────────┘
```

### Was passiert im Newsletter-Script?

1. **TMDB API:** Holt Top Filme & Serien
2. **Ollama AI:** Wählt beste 5 Filme + 5 Serien
3. **Plex Stats:** Holt Watch-Statistik
4. **HTML generieren:** Erstellt Newsletter
5. **NAS speichern:** `weekly_newsletter_YYYY-MM-DD.html`
6. **JSON Index:** Erstellt/aktualisiert `index.json` ← **NEU**
7. **Trilium:** Erstellt Notiz in Trilium
8. **Push Notification:** Sendet Push an Family Hub ← **NEU**

---

## Troubleshooting

### Problem: Newsletter-Script läuft nicht

**Symptome:**
- n8n zeigt Error
- Kein HTML-File erstellt
- Exit Code != 0

**Lösungen:**
```bash
# 1. Python-Pfad prüfen
python --version

# 2. Dependencies prüfen
pip install requests

# 3. Manuell testen
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# 4. Logs checken
cat "\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log"
```

### Problem: Push Notification kommt nicht an

**Symptome:**
- Script erfolgreich
- Aber keine Push auf Phone

**Lösungen:**
```bash
# 1. Family Hub Backend läuft?
curl http://192.168.188.150:8000/

# 2. Push Subscriptions vorhanden?
curl http://192.168.188.150:8000/api/push/notify \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "body": "Test Push"}'

# 3. Checke Backend Logs
journalctl -u familyhub -f

# 4. VAPID Keys konfiguriert?
# Siehe backend/main.py Zeilen 50-60
```

**Wenn keine Subscriptions:**
1. Öffne Family Hub App im Browser
2. Klicke "Enable Notifications"
3. Erlaube Notifications im Browser
4. Checke dass Subscription gespeichert wurde

### Problem: JSON Index nicht erstellt

**Symptome:**
- Script erfolgreich
- Aber `index.json` fehlt

**Lösungen:**
```bash
# 1. NAS-Zugriff prüfen
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# 2. Schreibrechte prüfen
touch "\\192.168.188.6\Backups\Homelab\reports\newsletters\test.txt"

# 3. Verzeichnis erstellen
mkdir -p "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# 4. Manuell testen
python -c "
from pathlib import Path
import json
path = Path(r'\\192.168.188.6\Backups\Homelab\reports\newsletters\index.json')
path.write_text(json.dumps([{'test': 'ok'}]))
print('Test OK')
"
```

### Problem: n8n Workflow startet nicht automatisch

**Symptome:**
- Freitag 12:00 vorbei
- Aber kein Newsletter

**Lösungen:**
1. **Workflow aktiviert?**
   - Öffne n8n
   - Prüfe Toggle "Active" ist ON (grün)

2. **Schedule korrekt?**
   - Schedule Node öffnen
   - Cron: `0 12 * * 5` (Freitag 12:00)
   - Timezone: Prüfe Server-Timezone

3. **Manuell testen:**
   - Klicke "Execute Workflow"
   - Checke jeden Node

4. **n8n Logs:**
   ```bash
   # Docker Logs (falls n8n in Docker)
   docker logs -f n8n

   # Journalctl (falls systemd)
   journalctl -u n8n -f
   ```

---

## Testing

### Manueller Test - Newsletter-Script

```bash
# 1. Script ausführen
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# 2. Checke Output
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# Expected:
# - weekly_newsletter_2025-10-11.html
# - index.json

# 3. Checke index.json
cat "\\192.168.188.6\Backups\Homelab\reports\newsletters\index.json"

# Expected:
# [
#   {
#     "date": "2025-10-11",
#     "title": "Weekly Media Newsletter - KW 41",
#     "path": "weekly_newsletter_2025-10-11.html",
#     "movies": [...],
#     "shows": [...]
#   }
# ]
```

### Manueller Test - Push Notification

```bash
# Test Push Endpoint
curl -X POST http://192.168.188.150:8000/api/push/notify \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Newsletter",
    "body": "Dies ist ein Test",
    "url": "/index.html#newsletter"
  }'

# Expected Response:
# {
#   "success": 1,
#   "failed": 0,
#   "total_subscriptions": 1
# }
```

### Manueller Test - Newsletter Reload

```bash
curl -X POST http://192.168.188.150:8000/api/newsletter/reload

# Expected Response:
# {
#   "success": true,
#   "newsletter": {
#     "date": "2025-10-11",
#     "title": "...",
#     "movies": [...],
#     "shows": [...]
#   },
#   "push_sent": 1,
#   "push_failed": 0
# }
```

---

## API Endpoints

### POST `/api/push/notify`

Sendet Push Notification an alle Subscriber.

**Request:**
```json
{
  "title": "Newsletter verfügbar",
  "body": "Deine wöchentlichen Highlights sind da!",
  "url": "/index.html#newsletter"
}
```

**Response:**
```json
{
  "success": 2,
  "failed": 0,
  "total_subscriptions": 2
}
```

### POST `/api/newsletter/reload`

Lädt Newsletter Index und sendet Push.

**Response:**
```json
{
  "success": true,
  "newsletter": {
    "date": "2025-10-11",
    "title": "Weekly Media Newsletter - KW 41",
    "path": "weekly_newsletter_2025-10-11.html",
    "movies": [
      {
        "title": "Movie Title",
        "rating": 8.5,
        "reason": "Highly rated action thriller..."
      }
    ],
    "shows": [...]
  },
  "push_sent": 2,
  "push_failed": 0
}
```

---

## Dateien-Übersicht

### Geänderte Dateien:
- ✅ `C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py`
  - `extract_ai_reason()` hinzugefügt
  - `generate_json_index()` hinzugefügt
  - `send_push_notification()` hinzugefügt
  - `main()` erweitert

- ✅ `C:\Users\trapp\family-hub-improved\backend\main.py`
  - `/api/push/notify` erweitert
  - `/api/newsletter/reload` hinzugefügt

### Neue Dateien:
- ✅ `C:\Users\trapp\family-hub-improved\n8n\weekly_newsletter_workflow.json`
- ✅ `C:\Users\trapp\family-hub-improved\n8n\README.md`
- ✅ `C:\Users\trapp\family-hub-improved\test_integration.py`
- ✅ `C:\Users\trapp\family-hub-improved\NEWSLETTER_INTEGRATION.md`

### Backups:
- ✅ `C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py.backup`
- ✅ `C:\Users\trapp\family-hub-improved\backend\main.py.backup`

---

## Produktiv-Betrieb

### 1. Initial Setup (einmalig)

```bash
# 1. Newsletter-Script einmal manuell ausführen
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# 2. Family Hub Backend starten (oder als Service)
cd C:\Users\trapp\family-hub-improved\backend
python main.py

# 3. n8n Workflow importieren und aktivieren
# Siehe "Schritt 5: n8n Workflow importieren" oben
```

### 2. Monitoring

**Checke jeden Freitag um 12:05 Uhr:**

```bash
# 1. Newsletter erstellt?
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters" | tail -n 1

# 2. Logs checken
tail -n 50 "\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log"

# 3. n8n Execution checken
# Öffne n8n UI → Executions Tab → Checke letzte Ausführung

# 4. Push Notification erhalten?
# Checke Phone/Browser
```

### 3. Wartung

**Wöchentlich:**
- Prüfe n8n Execution Logs
- Prüfe dass Push Notifications ankommen

**Monatlich:**
- Prüfe Newsletter Index Größe (max 50 Einträge automatisch)
- Prüfe alte HTML-Files löschen falls zu viele (optional)

**Bei Problemen:**
1. Checke Logs
2. Teste manuell mit `test_integration.py`
3. Prüfe NAS-Zugriff
4. Prüfe Family Hub Backend läuft

---

## Feature-Roadmap

### Bereits implementiert:
- ✅ Automatische Newsletter-Generierung
- ✅ JSON Index für Frontend
- ✅ Push Notifications
- ✅ n8n Workflow-Automation
- ✅ Trilium Integration
- ✅ Overseerr Integration

### Geplant (optional):
- ⏳ Newsletter-Archiv im Frontend
- ⏳ Newsletter-Vorschau in Push Notification
- ⏳ Newsletter-Statistiken (Views, Klicks)
- ⏳ E-Mail-Versand (optional)
- ⏳ Newsletter-Personalisierung (User-Profile)

---

## Support

Bei Problemen:
1. Checke Logs (siehe Troubleshooting)
2. Teste mit `test_integration.py`
3. Prüfe n8n Execution Logs
4. Prüfe Family Hub Backend Logs

**Logs:**
- Newsletter: `\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log`
- Family Hub: `journalctl -u familyhub -f`
- n8n: n8n UI → Executions Tab

---

**Erstellt:** 2025-10-11
**Version:** 1.0
**Author:** Qwen3-Coder 30B + Claude Code
