# Newsletter + Family Hub Integration - Zusammenfassung

## Was wurde gemacht?

### 1. Newsletter-Script erweitert ✅
**Datei:** `C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py`

**3 neue Funktionen hinzugefügt:**
1. `extract_ai_reason()` - Extrahiert AI-Empfehlung aus MediaItem
2. `generate_json_index()` - Erstellt `index.json` für Family Hub
3. `send_push_notification()` - Sendet Push an Family Hub Backend

**Integration in main():**
- Nach `save_report()` → JSON Index erstellen
- Nach Trilium Update → Push Notification senden
- Fehlertoleranz: Warnings statt Errors

### 2. Family Hub Backend erweitert ✅
**Datei:** `C:\Users\trapp\family-hub-improved\backend\main.py`

**Änderungen:**
1. `/api/push/notify` → Akzeptiert jetzt flexible Dict-Payload mit `url` Parameter
2. `/api/newsletter/reload` → Neuer Endpoint für Newsletter-Updates

### 3. n8n Workflow erstellt ✅
**Dateien:**
- `n8n/weekly_newsletter_workflow.json` - Workflow-Definition
- `n8n/README.md` - Import & Setup-Anleitung

**Workflow:**
```
Schedule (Freitag 12:00)
  → Execute Newsletter Script
    → IF Success
      → Send Push Notification
        → Log Success
    → ELSE
      → Log Error
```

### 4. Test-Script erstellt ✅
**Datei:** `test_integration.py`

**Tests:**
1. Family Hub API Health Check
2. Push Notification Endpoint
3. NAS-Zugriff
4. Newsletter Index
5. Newsletter Reload Endpoint

### 5. Dokumentation erstellt ✅
**Dateien:**
- `NEWSLETTER_INTEGRATION.md` - Vollständige Doku (50+ Seiten)
- `INTEGRATION_SUMMARY.md` - Diese Zusammenfassung

---

## Wie testet man?

### Quick Test (5 Minuten)

```bash
# 1. Integration testen
cd C:\Users\trapp\family-hub-improved
python test_integration.py

# Erwarte: "✅ ALL TESTS PASSED"

# 2. Newsletter-Script manuell ausführen
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# Erwarte:
# - HTML-File erstellt
# - index.json erstellt/aktualisiert
# - Push Notification gesendet

# 3. Output prüfen
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# Erwarte:
# - weekly_newsletter_YYYY-MM-DD.html
# - index.json
```

### n8n Workflow testen (10 Minuten)

```bash
# 1. Öffne n8n
http://192.168.188.131:5678

# 2. Importiere Workflow
# "+" → "Import from File" → weekly_newsletter_workflow.json

# 3. Konfiguriere (falls nötig)
# - Python-Pfad prüfen
# - Family Hub IP prüfen (192.168.188.150)

# 4. Teste manuell
# Klicke "Execute Workflow" (Play-Button)

# 5. Checke Logs
# Jeder Node zeigt Output

# 6. Aktiviere
# Toggle "Active" auf ON
```

---

## n8n Workflow Import - Schritt für Schritt

### 1. n8n öffnen
```
http://192.168.188.131:5678
```

### 2. Neuer Workflow
- Klicke **"+"** (oben links)
- Oder: **"New Workflow"**

### 3. Import
- Klicke **"..." Menü** (oben rechts)
- Wähle **"Import from File"**
- Wähle: `C:\Users\trapp\family-hub-improved\n8n\weekly_newsletter_workflow.json`

### 4. Workflow prüfen

**Schedule Node:**
- Trigger: Freitag 12:00 Uhr
- Cron: `0 12 * * 5`
- ✅ Passt für wöchentlichen Newsletter

**Execute Command Node:**
- Command: `python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"`
- ⚠️ Prüfe Python-Pfad!
- Falls Python nicht im PATH: Absoluten Pfad verwenden

**HTTP Request Node:**
- URL: `http://192.168.188.150:8000/api/push/notify`
- Method: POST
- Body: JSON mit title, body, url
- ⚠️ Prüfe IP-Adresse!

### 5. Manuell testen
- Klicke **"Execute Workflow"** (Play-Button, oben rechts)
- Warte auf Completion (~2-5 Minuten)
- Checke jeden Node:
  - ✅ Grün = Success
  - ❌ Rot = Error

**Bei Success:**
- Newsletter wurde erstellt
- JSON Index aktualisiert
- Push Notification gesendet

**Bei Error:**
- Klicke auf roten Node
- Checke Error-Message
- Siehe Troubleshooting unten

### 6. Aktivieren
- Toggle **"Active"** (oben rechts) auf **ON** (grün)
- Workflow läuft jetzt automatisch jeden Freitag um 12:00 Uhr

---

## Troubleshooting

### ❌ "Newsletter-Script fehlgeschlagen"

**Problem:** Execute Command Node zeigt Error

**Lösungen:**
```bash
# 1. Python-Pfad prüfen
where python

# 2. Manuell testen
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# 3. Dependencies installieren
pip install requests

# 4. Logs checken
cat "\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log"
```

### ❌ "Push Notification failed"

**Problem:** HTTP Request Node zeigt Error oder success=0

**Lösungen:**
```bash
# 1. Family Hub läuft?
curl http://192.168.188.150:8000/

# 2. Push Subscriptions vorhanden?
# → Öffne Family Hub App
# → Klicke "Enable Notifications"
# → Erlaube im Browser

# 3. Test Push
curl -X POST http://192.168.188.150:8000/api/push/notify \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Test Push"}'

# Erwarte: {"success": 1, "failed": 0}
```

### ❌ "JSON Index nicht erstellt"

**Problem:** index.json fehlt oder leer

**Lösungen:**
```bash
# 1. NAS-Zugriff prüfen
ls "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# 2. Verzeichnis erstellen
mkdir -p "\\192.168.188.6\Backups\Homelab\reports\newsletters"

# 3. Schreibrechte prüfen
touch "\\192.168.188.6\Backups\Homelab\reports\newsletters\test.txt"
```

### ❌ "n8n Workflow startet nicht automatisch"

**Problem:** Freitag 12:00 vorbei, aber kein Newsletter

**Lösungen:**
1. **Workflow aktiviert?**
   - Toggle "Active" ist ON (grün)?

2. **Schedule korrekt?**
   - Cron: `0 12 * * 5`
   - Timezone: Server-Zeit prüfen

3. **n8n läuft?**
   ```bash
   # Docker
   docker ps | grep n8n

   # Service
   systemctl status n8n
   ```

---

## Quick Reference

### Dateien

| Datei | Pfad |
|-------|------|
| Newsletter-Script | `C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py` |
| Family Hub Backend | `C:\Users\trapp\family-hub-improved\backend\main.py` |
| n8n Workflow | `C:\Users\trapp\family-hub-improved\n8n\weekly_newsletter_workflow.json` |
| Test-Script | `C:\Users\trapp\family-hub-improved\test_integration.py` |
| Doku | `C:\Users\trapp\family-hub-improved\NEWSLETTER_INTEGRATION.md` |

### URLs

| Service | URL |
|---------|-----|
| n8n | http://192.168.188.131:5678 |
| Family Hub | http://192.168.188.150:8000 |
| Plex | http://192.168.188.7:32400 |
| Overseerr | http://192.168.188.79:5055 |

### Logs

| Service | Log-Pfad |
|---------|----------|
| Newsletter | `\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log` |
| Family Hub | `journalctl -u familyhub -f` |
| n8n | n8n UI → Executions Tab |

### Output

| File | Pfad |
|------|------|
| HTML Newsletter | `\\192.168.188.6\Backups\Homelab\reports\newsletters\weekly_newsletter_YYYY-MM-DD.html` |
| JSON Index | `\\192.168.188.6\Backups\Homelab\reports\newsletters\index.json` |

---

## Checkliste: Produktiv-Setup

- [ ] Newsletter-Script einmal manuell getestet
- [ ] Family Hub Backend läuft
- [ ] test_integration.py erfolgreich (5/5 Tests)
- [ ] n8n Workflow importiert
- [ ] n8n Workflow manuell getestet (erfolgreich)
- [ ] n8n Workflow aktiviert (Toggle ON)
- [ ] Push Subscriptions vorhanden (in Family Hub App)
- [ ] Erste Newsletter-Ausführung erfolgreich (Freitag 12:00)
- [ ] Push Notification erhalten

---

## Nächste Schritte

1. **Jetzt:** Teste mit `test_integration.py`
2. **Dann:** Importiere n8n Workflow
3. **Test:** Führe Workflow manuell aus
4. **Aktiviere:** Toggle "Active" in n8n
5. **Warten:** Erster automatischer Lauf am Freitag 12:00 Uhr

---

## Support

**Dokumentation:** `NEWSLETTER_INTEGRATION.md` (vollständig)
**Quick Help:** Diese Datei

**Bei Problemen:**
1. Checke Logs (siehe Quick Reference)
2. Lese Troubleshooting (siehe oben)
3. Teste mit `test_integration.py`

---

**Viel Erfolg! 🚀**
