# iOS Push Notifications Setup Guide

## Voraussetzungen für iOS Push-Benachrichtigungen

Apple unterstützt Push-Benachrichtigungen in PWAs seit **iOS 16.4** (März 2023).

### Wichtige Anforderungen:

1. **HTTPS ist zwingend erforderlich**
   - Die App muss über HTTPS erreichbar sein
   - Localhost funktioniert nur für Tests auf dem Desktop

2. **PWA muss installiert sein**
   - Push funktioniert NUR wenn die App über "Zum Home-Bildschirm hinzufügen" installiert wurde
   - Browser-Push (Safari Tab) wird NICHT unterstützt

3. **iOS Version**
   - Mindestens iOS 16.4 oder neuer
   - iPadOS 16.4 oder neuer

## Schritt-für-Schritt Anleitung

### 1. App über HTTPS öffnen

Öffne die Family Hub App über deine HTTPS-URL:
```
https://deine-domain.de
```

### 2. PWA installieren

1. Tippe auf das **Teilen-Symbol** (Quadrat mit Pfeil nach oben) in Safari
2. Scrolle nach unten und wähle **"Zum Home-Bildschirm"**
3. Bestätige mit **"Hinzufügen"**

### 3. Installierte App öffnen

- Öffne die App vom Home-Bildschirm (NICHT über Safari!)
- Die App sollte im Vollbild-Modus ohne Safari-UI laufen

### 4. Push-Benachrichtigungen aktivieren

1. Tippe auf das **Glocken-Symbol** (🔔) oben rechts
2. Tippe auf **"Push aktivieren"**
3. Erlaube Benachrichtigungen wenn iOS fragt

### 5. Test-Benachrichtigung senden

#### Option A: Über Admin-Panel
1. Gehe zu `/admin.html`
2. Login mit Admin-Credentials
3. Sende eine Test-Push-Benachrichtigung

#### Option B: Über API
```bash
curl -X POST https://deine-domain.de/api/push/admin/send \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "title": "Test Notification",
    "body": "Dies ist eine Test-Benachrichtigung für iOS",
    "url": "/",
    "icon": "/assets/icons/app-icon-192.png"
  }'
```

## Troubleshooting

### Push-Benachrichtigungen funktionieren nicht

**Problem:** Button "Push aktivieren" zeigt Fehlermeldung

**Lösung:**
1. Prüfe ob die App als PWA installiert ist (nicht über Safari-Browser)
2. Prüfe iOS Version: Einstellungen → Allgemein → Info → Softwareversion
3. Prüfe ob HTTPS verwendet wird (nicht HTTP)
4. Prüfe Browser Console für Fehler

**Problem:** Subscription wird nicht erstellt

**Lösung:**
1. Deinstalliere die PWA komplett
2. Lösche Safari Cache: Einstellungen → Safari → Verlauf und Websitedaten löschen
3. Installiere die PWA neu
4. Versuche Push-Aktivierung erneut

**Problem:** Keine Benachrichtigungen obwohl subscribed

**Lösung:**
1. Prüfe iOS Einstellungen → Mitteilungen → Family Hub
2. Stelle sicher dass "Mitteilungen erlauben" aktiviert ist
3. Prüfe Backend-Logs auf Fehler beim Senden
4. Teste mit `/push-debug.html` für detaillierte Diagnose

### Benachrichtigungen kommen mit Verzögerung

**Ursache:** iOS Power Management

**Verhalten:**
- Benachrichtigungen können verzögert werden wenn das Gerät im Low-Power-Mode ist
- Background-Push kann bis zu 15 Minuten dauern
- Sofortige Zustellung nur wenn App kürzlich benutzt wurde

**Lösung:**
- Dies ist normales iOS-Verhalten
- Wichtige Benachrichtigungen sollten "time-sensitive" markiert werden (noch nicht implementiert)

## Debug-Tools

### Push Debug Seite
Öffne `/push-debug.html` für detaillierte Informationen:
- Service Worker Status
- Push Subscription Status
- VAPID Key Konfiguration
- Subscription Endpoint (anonymisiert)

### Browser Console
Aktiviere Web Inspector in iOS Safari:
1. Einstellungen → Safari → Erweitert → Web-Inspektor aktivieren
2. Verbinde iPhone mit Mac
3. Safari auf Mac → Entwickler → [Dein iPhone] → Family Hub
4. Console Tab für Logs

### Backend Debug
Admin-Endpunkt für Backend-Status:
```
GET /api/push/debug
```

Zeigt:
- Anzahl Subscriptions
- VAPID Key Status
- Provider Breakdown (Apple, Google, Mozilla)
- Sample Endpoints

## Apple-Spezifische Limits

### Notification-Features
iOS unterstützt aktuell (Stand iOS 17):
- ✅ Titel und Body
- ✅ Icon und Badge
- ✅ Click-Action (URL öffnen)
- ❌ Notification Actions (Buttons)
- ❌ Vibration Patterns
- ❌ Silent Notifications

### Subscription-Limits
- Keine bekannten Limits für Subscription-Anzahl
- Subscriptions bleiben aktiv auch wenn App geschlossen
- Subscriptions können von iOS ohne Warnung invalidiert werden

## Best Practices

1. **User Experience**
   - Zeige klare Anleitung für PWA-Installation
   - Erkläre Vorteile von Push-Benachrichtigungen
   - Respektiere "Später" - nerve nicht mit Popups

2. **Timing**
   - Frage nach Push-Permission nach PWA-Installation
   - Nicht sofort beim ersten App-Start
   - Nach erster erfolgreicher Aktion (z.B. Newsletter gelesen)

3. **Error Handling**
   - Zeige hilfreiche Fehlermeldungen
   - Biete alternative Benachrichtigungsmethoden (E-Mail)
   - Handle Subscription-Expiration gracefully

4. **Testing**
   - Teste auf echten iOS-Geräten (Simulator unterstützt kein Push)
   - Teste verschiedene iOS-Versionen
   - Teste Low-Power-Mode und Background-Verhalten

## Weitere Ressourcen

- [Apple Documentation: Push Notifications in Web Apps](https://developer.apple.com/documentation/usernotifications/sending_web_push_notifications_in_web_apps_and_browsers)
- [Web.dev: iOS Push Notifications](https://web.dev/push-notifications-web-push-protocol/)
- [Can I Use: Push API](https://caniuse.com/push-api)

## Support

Bei Problemen:
1. Prüfe `/push-debug.html`
2. Prüfe Backend-Logs
3. Prüfe iOS System-Logs (Console.app auf Mac)
4. Erstelle Issue mit Debug-Informationen
