# n8n Workflow für Weekly Newsletter

## Import-Anleitung

1. Öffne n8n: http://192.168.188.131:5678
2. Klicke auf "+" → "Import from File"
3. Wähle `weekly_newsletter_workflow.json`
4. Workflow wird importiert

## Konfiguration

### 1. Execute Command Node anpassen
- Passe den Python-Pfad an falls anders
- Standard: `python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"`

### 2. HTTP Request Node prüfen
- URL: `http://192.168.188.150:8000/api/push/notify`
- Passe IP an falls Family Hub auf anderer IP läuft

### 3. Schedule anpassen (optional)
- Standard: Freitag 12:00 Uhr
- Cron: `0 12 * * 5`
- Ändern falls gewünscht

## Testing

1. Klicke auf "Execute Workflow" (Play-Button)
2. Prüfe Log-Output
3. Checke ob Newsletter erstellt wurde
4. Checke ob Push Notification gesendet wurde

## Troubleshooting

### Script läuft nicht
- Prüfe Python-Pfad in Execute Command
- Checke Script-Permissions
- Schaue in n8n Error-Log

### Push kommt nicht an
- Prüfe Family Hub Backend läuft
- Checke IP-Adresse korrekt
- Schaue in Family Hub Logs: `journalctl -u familyhub -f`

### Newsletter Index nicht erstellt
- Prüfe NAS-Zugriff: `\\192.168.188.6\Backups\Homelab\reports\newsletters\`
- Checke Schreibrechte
- Schaue in Script-Logs

## Workflow-Details

### Nodes:

1. **Schedule - Freitag 12:00**
   - Trigger: Jeden Freitag um 12:00 Uhr
   - Cron: `0 12 * * 5`

2. **Execute Newsletter Script**
   - Führt Python-Script aus
   - Timeout: 5 Minuten

3. **IF Success**
   - Prüft Exit-Code
   - Code 0 = Success
   - Code != 0 = Error

4. **Send Push Notification**
   - Sendet Push an Family Hub API
   - Body: JSON mit title, body, url

5. **Log Success**
   - Loggt erfolgreiche Ausführung
   - Zeigt Push-Stats

6. **Log Error**
   - Loggt Fehler
   - Zeigt stderr output

## Manueller Test

Teste das Script manuell bevor du n8n verwendest:

```bash
# Test Newsletter-Script
python "C:\Users\trapp\homelab\scripts\media\weekly_newsletter.py"

# Test Push Notification
curl -X POST http://192.168.188.150:8000/api/push/notify \
  -H "Content-Type: application/json" \
  -d '{"title": "Test", "body": "Test Push", "url": "/"}'
```

## Produktiv-Verwendung

1. Importiere Workflow in n8n
2. Teste einmal manuell
3. Aktiviere Workflow (Toggle oben rechts)
4. Workflow läuft automatisch jeden Freitag um 12:00 Uhr

## Logs

- n8n Logs: In n8n UI unter "Executions"
- Script Logs: `\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log`
- Family Hub Logs: `journalctl -u familyhub -f`
