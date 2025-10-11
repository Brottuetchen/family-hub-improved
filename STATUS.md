# Family Hub – Status Snapshot (2025-10-11)

Dieser Snapshot fasst den aktuellen Projektstand zusammen und dient als Startpunkt für die weitere Arbeit (z. B. durch Codex).

## Fertiggestellt
- Weekly-Newsletter-Skript (`homelab/scripts/media/weekly_newsletter_codex.py`) erzeugt HTML + JSON-Index, aktualisiert Trilium und Plex-Statistiken.
- Family-Hub-PWA (`public/`) und FastAPI-Backend (`backend/`) sind funktionsfähig und lokal getestet.
- `newsletters/index.json` wird beim Skriptlauf automatisch befüllt und in die Web-App kopiert.
- n8n-Workflow (`n8n/weekly_newsletter_workflow.json`) triggert das Skript, ruft `/api/newsletter/reload` und `/api/push/notify` auf.
- Umfangreiche Dokumentation vorhanden (`README.md`, `PROJECT_STATUS.md`, `CODEX_HANDOFF.md` u. a.).

## Offene Punkte
1. **Backend deployen:** FastAPI-Service auf dem vorgesehenen LXC (192.168.188.150) starten – aktuell laufen Push-Requests in ein Timeout.
2. **VAPID Keys generieren:** `python backend/generate_vapid_keys.py` ausführen und Keys in `backend/main.py` eintragen.
3. **PNG-App-Icons exportieren:** Aus `public/assets/icons/app-icon.svg` Icons in 192 px & 512 px erzeugen.
4. **n8n importieren & aktivieren:** Workflow in n8n importieren, URLs prüfen, Toggle aktivieren.
5. **End-to-End-Test:** PWA öffnen, Push erlauben, Newsletter-Skript ausführen und Erfolg im Browser (Notification) verifizieren.

## Relevante Pfade
- Newsletter-Script: `C:\Users\trapp\homelab\scripts\media\weekly_newsletter_codex.py`
- Web-App & Backend: `C:\Users\trapp\family-hub-improved\`
- NAS-Ziel: `\\192.168.188.6\Backups\Homelab\reports\newsletters\`
- n8n Workflow: `family-hub-improved\n8n\weekly_newsletter_workflow.json`

## Hinweise
- `ENABLE_FAMILY_HUB_PUSH` kann temporär auf `false` stehen, solange das Backend nicht erreichbar ist.
- Logs liegen unter `\\192.168.188.6\Backups\Homelab\reports\logs\weekly_newsletter.log` bzw. in n8n (`Executions`).
- Details zu Setup & Deployment siehe `README.md`, `QUICKSTART.md`, `PROJECT_STATUS.md`, `CODEX_HANDOFF.md`.

_Letzte Aktualisierung: 2025‑10‑11, Claude (Codex-Vorbereitung)_
