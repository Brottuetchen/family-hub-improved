# Family Hub - Lokaler Betrieb (ohne Cloudflare)

## Übersicht

Diese Anleitung zeigt, wie du Family Hub nur lokal und über VPN erreichbar machst, während Push Notifications weiterhin funktionieren.

## Wichtige Anforderungen

### Push Notifications benötigen:
1. ✅ **HTTPS** (auch lokal!)
2. ✅ **Service Worker** (läuft nur mit HTTPS)
3. ✅ **VAPID Keys** (bereits konfiguriert)

### Problem ohne Cloudflare:
- iOS Safari akzeptiert nur HTTPS für Push Notifications
- Self-signed Certificates werden von iOS oft blockiert
- Lösung: **Lokale CA** oder **Let's Encrypt mit DNS Challenge**

---

## Option 1: Cloudflare Proxy deaktivieren (empfohlen)

### Vorteile:
- ✅ Gültiges Let's Encrypt Zertifikat
- ✅ Push Notifications funktionieren auf iOS
- ✅ Nur über VPN erreichbar (durch Firewall-Regeln)

### Schritte:

#### 1. Cloudflare DNS auf "DNS-Only" setzen

1. Login zu Cloudflare: https://dash.cloudflare.com/
2. Wähle Domain `t-acc.com`
3. Gehe zu **DNS** → **Records**
4. Finde den Eintrag `family.t-acc.com`
5. Klicke auf die **orangene Cloud** (Proxy enabled)
6. Wähle **DNS only** (graue Cloud)
7. Speichern

**Ergebnis:** DNS-Auflösung funktioniert weiterhin, aber Cloudflare cached nichts mehr.

#### 2. Firewall-Regel auf Proxmox/Router

```bash
# Auf deinem Router/Firewall (z.B. OPNsense/pfSense):
# Erstelle Regel: Erlaube Port 443 zu 192.168.188.123 nur von VPN-Netzwerk

# Beispiel für iptables (falls direkt auf Proxmox):
iptables -A INPUT -p tcp --dport 443 -s 192.168.188.0/24 -j ACCEPT  # Lokales Netz
iptables -A INPUT -p tcp --dport 443 -s 10.8.0.0/24 -j ACCEPT      # VPN-Netz (anpassen!)
iptables -A INPUT -p tcp --dport 443 -j DROP                        # Alle anderen blockieren
```

#### 3. Nginx Proxy Manager Konfiguration beibehalten

- NPM liefert weiterhin Let's Encrypt Zertifikat
- HTTPS funktioniert → Push Notifications funktionieren
- Nur noch über VPN/lokales Netz erreichbar

---

## Option 2: Self-Signed Certificate (nicht empfohlen für iOS)

### Problem:
iOS Safari blockiert Service Worker mit self-signed Certificates, außer:
- Zertifikat ist in iOS installiert UND
- Domain ist in "Certificate Trust Settings" aktiviert

### Schritte (falls Option 1 nicht möglich):

#### 1. Eigene CA erstellen

```bash
# Auf LXC 123 (familyweb):
cd /opt/family-hub-improved

# CA Key erstellen
openssl genrsa -out ca-key.pem 4096

# CA Certificate erstellen
openssl req -x509 -new -nodes -key ca-key.pem \
  -sha256 -days 3650 -out ca-cert.pem \
  -subj "/C=DE/ST=NRW/L=Stadt/O=Homelab/CN=Family Hub CA"

# Server Key erstellen
openssl genrsa -out server-key.pem 2048

# Server CSR erstellen
openssl req -new -key server-key.pem -out server-csr.pem \
  -subj "/C=DE/ST=NRW/L=Stadt/O=Homelab/CN=family.local"

# Server Zertifikat signieren
openssl x509 -req -in server-csr.pem -CA ca-cert.pem -CAkey ca-key.pem \
  -CAcreateserial -out server-cert.pem -days 365 -sha256 \
  -extfile <(printf "subjectAltName=DNS:family.local,IP:192.168.188.123")
```

#### 2. Zertifikat auf iOS installieren

1. Kopiere `ca-cert.pem` auf iPhone (z.B. per AirDrop)
2. Öffne Datei → Installiere Profil
3. Gehe zu **Einstellungen** → **Allgemein** → **Info** → **Zertifikatsvertrauensstellung**
4. Aktiviere CA für "family.local"

#### 3. Nginx mit eigenem Zertifikat konfigurieren

In Nginx Proxy Manager:
- Custom Certificate hochladen
- `server-cert.pem` + `server-key.pem` verwenden

**Problem:** Bei Zertifikat-Erneuerung (alle 365 Tage) muss iOS-Profil neu installiert werden.

---

## Option 3: Let's Encrypt DNS Challenge (beste Lösung)

### Vorteile:
- ✅ Gültiges Zertifikat
- ✅ Funktioniert ohne öffentlichen Port 80/443
- ✅ Push Notifications funktionieren einwandfrei
- ✅ Automatische Erneuerung

### Voraussetzung:
- Cloudflare API Token mit DNS-Schreibrechten

### Setup in Nginx Proxy Manager:

1. **SSL Certificate** → **Add SSL Certificate**
2. Wähle **Let's Encrypt**
3. Domain: `family.t-acc.com`
4. **Use a DNS Challenge**: ✅
5. DNS Provider: **Cloudflare**
6. Credentials File Content:
   ```ini
   dns_cloudflare_api_token = DEIN_CLOUDFLARE_API_TOKEN
   ```
7. Propagation Seconds: `30`
8. Save

**Ergebnis:**
- Gültiges Let's Encrypt Zertifikat
- Funktioniert auch wenn Port 80/443 von außen gesperrt sind
- Automatische Erneuerung alle 90 Tage

---

## VPN-Setup für externen Zugriff

### WireGuard auf Proxmox/Router einrichten

```bash
# Falls noch nicht installiert:
apt update && apt install wireguard

# WireGuard Konfiguration
cd /etc/wireguard
wg genkey | tee privatekey | wg pubkey > publickey

# Server Config erstellen
cat > wg0.conf <<EOF
[Interface]
PrivateKey = $(cat privatekey)
Address = 10.8.0.1/24
ListenPort = 51820
PostUp = iptables -A FORWARD -i wg0 -j ACCEPT; iptables -t nat -A POSTROUTING -o vmbr0 -j MASQUERADE
PostDown = iptables -D FORWARD -i wg0 -j ACCEPT; iptables -t nat -D POSTROUTING -o vmbr0 -j MASQUERADE

# Client 1 (iPhone)
[Peer]
PublicKey = CLIENT_PUBLIC_KEY
AllowedIPs = 10.8.0.2/32
EOF

# WireGuard starten
systemctl enable wg-quick@wg0
systemctl start wg-quick@wg0
```

### iPhone Client-Konfiguration

```ini
[Interface]
PrivateKey = CLIENT_PRIVATE_KEY
Address = 10.8.0.2/32
DNS = 192.168.188.3  # Pi-hole

[Peer]
PublicKey = SERVER_PUBLIC_KEY
Endpoint = DEINE_OEFFENTLICHE_IP:51820
AllowedIPs = 192.168.188.0/24, 10.8.0.0/24
PersistentKeepalive = 25
```

**App installieren:** WireGuard aus App Store

---

## Test nach Umstellung

### 1. HTTPS Funktioniert
```bash
curl -I https://family.t-acc.com
# Sollte 200 OK zurückgeben
```

### 2. Push Notifications testen

```bash
# Test-Push senden
curl -X POST https://family.t-acc.com/api/push/notify \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Notification",
    "body": "Push funktioniert!",
    "url": "/index.html"
  }'
```

### 3. Service Worker prüfen

1. Öffne https://family.t-acc.com in Browser
2. DevTools → Application → Service Workers
3. Status sollte "activated and running" sein

---

## Empfohlene Konfiguration

**Für maximale Sicherheit + funktionierende Push Notifications:**

1. ✅ **Option 3: Let's Encrypt DNS Challenge** verwenden
2. ✅ **Cloudflare Proxy deaktivieren** (DNS-only)
3. ✅ **Firewall-Regel**: Port 443 nur für lokales Netz + VPN
4. ✅ **WireGuard VPN** für externen Zugriff
5. ✅ **Pi-hole DNS** über VPN verfügbar machen

**Ergebnis:**
- Family Hub nur über lokales Netz oder VPN erreichbar
- Push Notifications funktionieren auf iOS
- Gültiges HTTPS-Zertifikat (Let's Encrypt)
- Keine Cloudflare-Caching-Probleme mehr

---

## Troubleshooting

### Push Notifications funktionieren nicht

1. **HTTPS prüfen:**
   ```bash
   openssl s_client -connect family.t-acc.com:443 -servername family.t-acc.com
   ```

2. **Service Worker Status:**
   - DevTools → Console: `navigator.serviceWorker.controller`
   - Sollte nicht `null` sein

3. **VAPID Keys prüfen:**
   ```bash
   curl https://family.t-acc.com/api/vapid-public-key
   # Sollte Public Key zurückgeben
   ```

### iOS blockiert Service Worker

- Prüfe ob Zertifikat gültig ist: Safari → Adressleiste → Schloss-Symbol
- Erzwinge Service Worker Neuregistrierung:
  ```javascript
  navigator.serviceWorker.getRegistrations().then(regs =>
    regs.forEach(reg => reg.unregister())
  );
  ```

### VPN-Verbindung bricht ab

- Erhöhe `PersistentKeepalive` in Client-Config (z.B. auf 25 Sekunden)
- Prüfe Firewall erlaubt UDP Port 51820

---

## Weitere Fragen?

Siehe auch:
- [CLOUDFLARE_SETUP.md](./CLOUDFLARE_SETUP.md) - Detaillierte Cloudflare-Konfiguration
- [NGINX_CONFIG.md](./NGINX_CONFIG.md) - Nginx Reverse Proxy Setup
- [PUSH_NOTIFICATIONS.md](./PUSH_NOTIFICATIONS.md) - Push Notification Details
