# YouTube to Podcast - n8n Workflow Dokumentation

## 🎯 Übersicht

Dieser n8n Workflow automatisiert den Download von YouTube-Videos und konvertiert sie in Podcast-Episoden für AudioBookshelf.

### Features:
- ✅ Überwacht 6 YouTube-Kanäle alle 30 Minuten
- ✅ Lädt die neuesten 3 Videos jedes Kanals als MP3 herunter
- ✅ Erstellt automatisch Podcast-Struktur mit Metadaten
- ✅ Scannt AudioBookshelf Library nach neuen Downloads
- ✅ Sendet Push-Benachrichtigung über Family Hub
- ✅ 3x Retry-Logik bei Download-Fehlern
- ✅ Überspringt bereits heruntergeladene Videos

---

## 📋 Voraussetzungen

### LXC Container Setup:
- **CT 112 (n8n):** yt-dlp installiert ✅, /mnt/nas gemountet ✅
- **CT 114 (AudioBookshelf):** `http://192.168.188.84:13378`
- **CT 123 (Family Hub):** `http://192.168.188.150:8000`

### Benötigte Credentials:
- **AudioBookshelf API Token:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...`
- **Family Hub Admin:** `xconsit17x@gmail.com` / `Surface2013!!`
- **Library ID:** `952b2028-1591-4f7e-b6e7-a7f1ce5f59e6`

### Speicherstruktur:
```
/mnt/nas/podcasts/
├── Malternativ/
│   ├── cover.jpg
│   ├── 20250119_Video_Titel.mp3
│   ├── 20250119_Video_Titel.jpg
│   └── 20250119_Video_Titel.txt (Beschreibung)
├── Simplicissimus/
│   └── ...
└── ...
```

---

## 🚀 Installation

### Schritt 1: Workflow importieren

1. Öffne n8n: `http://192.168.188.112:5678` (oder deine n8n URL)
2. Klicke auf **"+"** → **"Import from File"**
3. Wähle `n8n-youtube-podcast-workflow.json`
4. Workflow wird importiert ✅

### Schritt 2: Credentials überprüfen

Der Workflow verwendet **keine separaten Credentials** - alle Tokens sind direkt in den Nodes eingetragen:
- AudioBookshelf API Token (in "Scan AudioBookshelf Library" Node)
- Family Hub Login (in "Login to Family Hub" Node)

### Schritt 3: Test-Ausführung

1. **Deaktiviere den Cron-Trigger** (sonst läuft er alle 30 Min)
2. Klicke auf **"Execute Workflow"** für manuellen Test
3. Überwache die Logs in jedem Node

---

## 🔧 Workflow-Architektur

### Phase 1: Channel Processing (Loop über alle Kanäle)

```
Schedule Trigger (alle 30 Min)
  ↓
Set YouTube Channels (6 Kanäle als Array)
  ↓
Loop Channels (Split in Batches)
  ↓
Get Channel Page (YouTube Handle → HTML)
  ↓
Extract Channel ID (HTML → Channel ID via Regex)
  ↓
Fetch RSS Feed (YouTube RSS Feed)
  ↓
Parse RSS & Extract Videos (Neueste 3 Videos)
  ↓
Check if Already Downloaded (test -f)
  ↓
IF Not Downloaded
  ├─ TRUE → Download Pipeline
  └─ FALSE → Mark as Skipped
```

### Phase 2: Download Pipeline (für neue Videos)

```
Create Channel Directory (mkdir -p)
  ↓
Download with yt-dlp (MP3 + Thumbnail + Metadata)
  ↓  [3x Retry bei Fehler]
Prepare Metadata (Dateinamen, Pfade)
  ↓
Save Description (als .txt-Datei)
  ↓
Setup Podcast Cover (curl Channel-Logo)
  ↓
Mark as Downloaded
  ↓
Merge Download Results
  ↓
Loop zurück zu nächstem Video/Channel
```

### Phase 3: Post-Processing (nach allen Channels)

```
Aggregate Results (Zähle neue Downloads)
  ↓
IF New Downloads > 0
  ↓
Login to Family Hub (JWT Token holen)
  ↓
Scan AudioBookshelf Library (POST /api/libraries/.../scan)
  ↓
Wait for Scan to Complete (15 Sekunden)
  ↓
Prepare Push Notification (Zusammenfassung erstellen)
  ↓
Send Push Notification (Family Hub API)
  ↓
Workflow Complete
```

---

## 📊 Workflow-Nodes Erklärt

### 1. **Every 30 Minutes** (Schedule Trigger)
- **Typ:** `scheduleTrigger`
- **Intervall:** Alle 30 Minuten
- **Anpassen:** Ändere `minutesInterval` für andere Intervalle

### 2. **Set YouTube Channels**
- **Typ:** `set`
- **Funktion:** Definiert die 6 YouTube-Kanäle als Array
- **Channels:**
  - `@Malternativ`
  - `@2BoredGuysOfficial`
  - `@DieMeinungsmache`
  - `@Simplicissimus`
  - `@MrWissen2go`
  - `@MrWissen2goGeschichte`

### 3. **Loop Channels** (Split in Batches)
- **Typ:** `splitInBatches`
- **Batch Size:** 1 (ein Kanal nach dem anderen)
- **Funktion:** Iteriert über alle Kanäle

### 4. **Get Channel Page**
- **Typ:** `httpRequest`
- **URL:** `https://www.youtube.com/{{ handle }}`
- **Funktion:** Lädt die Channel-HTML-Seite

### 5. **Extract Channel ID** (Code Node)
- **Typ:** `code` (JavaScript)
- **Funktion:** Extrahiert Channel ID aus HTML via Regex
- **Methoden:**
  1. Sucht nach `"channelId":"UC..."`
  2. Sucht nach `"browseId":"UC..."`
  3. Sucht nach `"externalId":"UC..."`
- **Output:** `channelId`, `rssUrl`

### 6. **Fetch RSS Feed**
- **Typ:** `httpRequest`
- **URL:** `https://www.youtube.com/feeds/videos.xml?channel_id={channelId}`
- **Funktion:** Holt YouTube RSS Feed

### 7. **Parse RSS & Extract Videos** (Code Node)
- **Typ:** `code` (JavaScript)
- **Funktion:** Parsed XML und extrahiert neueste 3 Videos
- **Extrahiert:**
  - Video ID
  - Titel
  - Beschreibung
  - Thumbnail URL
  - Publish-Datum
- **Erstellt:** Safe filename (`YYYYMMDD_Titel.mp3`)

### 8. **Check if Already Downloaded**
- **Typ:** `executeCommand`
- **Command:** `test -f "/mnt/nas/podcasts/{channel}/{filename}"`
- **Output:** `exists` oder `not_exists`

### 9. **IF Not Downloaded**
- **Typ:** `if`
- **Condition:** stdout == "not_exists"
- **TRUE:** Weiter zum Download
- **FALSE:** Skip zu "Mark as Skipped"

### 10. **Create Channel Directory**
- **Typ:** `executeCommand`
- **Command:** `mkdir -p "/mnt/nas/podcasts/{channelName}"`

### 11. **Download with yt-dlp** ⭐
- **Typ:** `executeCommand`
- **Retry:** 3x bei Fehler, 5 Sekunden Pause
- **Command:**
```bash
cd "/mnt/nas/podcasts/{channelName}" && yt-dlp \
  --extract-audio \
  --audio-format mp3 \
  --audio-quality 0 \
  --embed-thumbnail \
  --embed-metadata \
  --add-metadata \
  --write-thumbnail \
  --convert-thumbnails jpg \
  --output "{filename}.%(ext)s" \
  "{videoUrl}"
```

### 12. **Prepare Metadata** (Code Node)
- **Typ:** `code`
- **Funktion:** Bereitet Dateinamen und Pfade vor

### 13. **Save Description**
- **Typ:** `executeCommand`
- **Command:** `echo "{description}" > "{metadataFile}"`

### 14. **Setup Podcast Cover**
- **Typ:** `executeCommand`
- **Funktion:** Lädt Channel-Logo als `cover.jpg` (nur wenn nicht vorhanden)

### 15. **Mark as Downloaded / Skipped**
- **Typ:** `set`
- **Funktion:** Setzt `downloaded: true/false` Flag

### 16. **Merge Download Results**
- **Typ:** `merge`
- **Funktion:** Merged beide Pfade (downloaded + skipped)

### 17. **Aggregate Results** (Code Node)
- **Typ:** `code`
- **Funktion:** Zählt neue Downloads und erstellt Zusammenfassung
- **Output:**
  - `newDownloads`: Anzahl neuer Videos
  - `skipped`: Anzahl übersprungener Videos
  - `channelsWithNewContent`: Array von Kanal-Namen
  - `videos`: Array von Video-Details

### 18. **IF New Downloads > 0**
- **Typ:** `if`
- **Condition:** `newDownloads > 0`
- **TRUE:** Weiter zu Push-Benachrichtigung
- **FALSE:** Workflow beenden (keine Notification)

### 19. **Login to Family Hub**
- **Typ:** `httpRequest`
- **Method:** POST
- **URL:** `http://192.168.188.150:8000/api/auth/login`
- **Body:**
```json
{
  "username": "xconsit17x@gmail.com",
  "password": "Surface2013!!"
}
```
- **Output:** `access_token` (JWT)

### 20. **Scan AudioBookshelf Library**
- **Typ:** `httpRequest`
- **Method:** POST
- **URL:** `http://192.168.188.84:13378/audiobookshelf/api/libraries/952b2028-1591-4f7e-b6e7-a7f1ce5f59e6/scan`
- **Headers:** `Authorization: Bearer {ABS_TOKEN}`

### 21. **Wait for Scan to Complete**
- **Typ:** `wait`
- **Duration:** 15 Sekunden
- **Funktion:** Gibt AudioBookshelf Zeit, den Scan abzuschließen

### 22. **Prepare Push Notification** (Code Node)
- **Typ:** `code`
- **Funktion:** Erstellt Push-Nachricht basierend auf Downloads
- **Logik:**
  - 1 neues Video: Zeige Video-Titel
  - 2-3 Videos: Zeige alle Titel
  - >3 Videos: Zeige Anzahl + Kanal-Namen

### 23. **Send Push Notification**
- **Typ:** `httpRequest`
- **Method:** POST
- **URL:** `http://192.168.188.150:8000/api/push/admin/send`
- **Headers:** `Authorization: Bearer {JWT_TOKEN}`
- **Body:**
```json
{
  "title": "🎙️ Neue Podcast-Episoden",
  "body": "{dynamische Zusammenfassung}",
  "url": "/",
  "icon": "/assets/icons/app-icon-192.png"
}
```

### 24. **Workflow Complete**
- **Typ:** `set`
- **Funktion:** Abschluss-Status setzen

---

## 🔒 Sicherheitshinweise

### Credentials im Workflow:
Der Workflow enthält folgende sensible Daten **direkt im JSON**:
- ❗ Family Hub Admin-Passwort
- ❗ AudioBookshelf API Token

**Empfehlung für Produktion:**
1. Erstelle n8n Credentials für:
   - AudioBookshelf (HTTP Header Auth)
   - Family Hub (Generic Credential)
2. Ersetze die hardcoded Werte durch Credential-Referenzen

### Passwort ändern:
Falls du das Family Hub Passwort änderst, musst du es in **2 Nodes** anpassen:
- Node: "Login to Family Hub" → Body Parameter `password`

---

## 🧪 Testing & Debugging

### Manueller Test:
1. Deaktiviere Cron-Trigger (setze auf "Inactive")
2. Klicke "Execute Workflow"
3. Prüfe jeden Node auf Fehler

### Häufige Fehler:

#### ❌ "yt-dlp: command not found"
**Lösung:** Installiere yt-dlp in CT 112:
```bash
lxc-attach -n 112
pip install yt-dlp
# oder
apt install yt-dlp
```

#### ❌ "Permission denied: /mnt/nas/podcasts"
**Lösung:** Prüfe Schreibrechte:
```bash
lxc-attach -n 112
touch /mnt/nas/podcasts/test.txt
rm /mnt/nas/podcasts/test.txt
```

#### ❌ "Channel ID not found"
**Ursache:** YouTube hat HTML-Struktur geändert
**Lösung:** Aktualisiere Regex in "Extract Channel ID" Node

#### ❌ "AudioBookshelf scan failed"
**Lösung:** Prüfe:
- Ist Library ID korrekt?
- Ist API Token gültig?
- Ist AudioBookshelf erreichbar?

#### ❌ "Family Hub login failed"
**Lösung:** Prüfe:
- Sind Credentials korrekt?
- Ist Family Hub erreichbar?
- Läuft das Backend?

### Debug-Logs aktivieren:
n8n zeigt alle Command-Outputs in den Nodes:
- Klicke auf Node → "View Details" → "Output"
- Prüfe `stdout` und `stderr`

---

## 📈 Monitoring

### Erfolgreiche Ausführung erkennen:
- Push-Benachrichtigung auf deinem Handy ✅
- Neue MP3s in `/mnt/nas/podcasts/{channel}/`
- AudioBookshelf zeigt neue Episoden

### Logs prüfen:
n8n Web UI:
- **Executions** → Liste aller Workflow-Runs
- **Execution Details** → Node-by-Node Logs

### Workflow-Status:
- **Grün:** Erfolgreich
- **Gelb:** Warnung (z.B. keine neuen Videos)
- **Rot:** Fehler

---

## 🛠️ Anpassungen

### Mehr/Weniger Kanäle:
Bearbeite Node: **"Set YouTube Channels"**
```javascript
[
  { "handle": "@NeuerKanal", "name": "Neuer Kanal" },
  // ... weitere Kanäle
]
```

### Intervall ändern:
Bearbeite Node: **"Every 30 Minutes"**
- Für stündlich: `minutesInterval: 60`
- Für täglich: Ändere zu `hours: 24`

### Anzahl Videos pro Kanal:
Bearbeite Node: **"Parse RSS & Extract Videos"**
```javascript
while ((match = entryRegex.exec(xml)) !== null && entries.length < 5) {
  // Ändere 3 → 5 für 5 Videos
}
```

### AudioBookshelf Library ändern:
Bearbeite Node: **"Scan AudioBookshelf Library"**
- Ändere Library ID in URL

### Push-Benachrichtigung anpassen:
Bearbeite Node: **"Prepare Push Notification"**
- Ändere Titel, Body-Format, Icon, URL

---

## 🚨 Troubleshooting

### Workflow läuft nicht alle 30 Min:
- Prüfe ob Trigger **aktiv** ist (grüner Toggle)
- Prüfe n8n Logs: `journalctl -u n8n -f` (wenn systemd)

### Videos werden nicht heruntergeladen:
1. Prüfe ob bereits vorhanden: `ls /mnt/nas/podcasts/{channel}/`
2. Prüfe yt-dlp manuell:
```bash
lxc-attach -n 112
yt-dlp --extract-audio --audio-format mp3 "https://www.youtube.com/watch?v={videoId}"
```

### Push kommt nicht an:
1. Prüfe Family Hub Logs
2. Teste Push manuell:
```bash
curl -X POST http://192.168.188.150:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"xconsit17x@gmail.com","password":"Surface2013!!"}'

# Mit Token:
curl -X POST http://192.168.188.150:8000/api/push/admin/send \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","body":"Test Message","url":"/","icon":"/assets/icons/app-icon-192.png"}'
```

### AudioBookshelf findet keine neuen Episoden:
1. Prüfe ob Dateien vorhanden: `ls /mnt/nas/podcasts/`
2. Prüfe AudioBookshelf Mount-Point (CT 114):
```bash
lxc-attach -n 114
ls /path/to/podcasts/
```
3. Triggere manuellen Scan in AudioBookshelf Web UI

---

## 📚 Weitere Optimierungen (Optional)

### 1. Datenbank-Tracking:
Statt File-Check eine SQLite DB für Download-Historie

### 2. Erweiterte Metadaten:
- Extrahiere Kapitel aus Beschreibung
- Setze Podcast-spezifische Tags (Genre: "Nachrichten")

### 3. Qualitäts-Optionen:
- Wähle verschiedene Audio-Qualitäten per Kanal
- z.B. Musik-Kanäle in höherer Qualität

### 4. Fehler-Benachrichtigung:
- Sende Push auch bei Fehlern (aktuell: keine Notification)

### 5. Deep-Links (später):
- Integriere ShelfPlayer Deep-Links
- `audiobookshelf://item/{itemId}`

---

## 🎉 Fertig!

Der Workflow ist jetzt einsatzbereit. Viel Spaß mit deinen automatischen Podcast-Downloads! 🚀

Bei Fragen oder Problemen:
1. Prüfe diese Doku
2. Prüfe n8n Execution Logs
3. Prüfe LXC Container Logs

**Happy Podcasting!** 🎙️
