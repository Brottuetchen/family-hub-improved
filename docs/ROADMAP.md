# Roadmap

Die Vision umfasst vier Phasen. Der aktuelle Stand ist das **Phase-1-MVP-Fundament**
inklusive Connector-Architektur und Hermes AI.

## Phase 1 – Kern (MVP)  ✅ umgesetzt
- [x] Login & Rollen (admin/partner/kind/gast)
- [x] Dashboard (aggregierte Tagesübersicht)
- [x] Kalender-Connector (CalDAV/Nextcloud)
- [x] Aufgaben (Vikunja: lesen + anlegen)
- [x] Einkauf (KitchenOwl: lesen + hinzufügen)
- [x] Erinnerungen & Pakete (Hermes-eigen)
- [x] Wiederkehrende Erinnerungen (täglich/werktags/wöchentlich/monatlich) mit Auto-Push
- [x] Wetter (Open-Meteo)
- [x] Push (Web Push / VAPID)
- [x] Hermes AI (Tools + Fallback)
- [x] Globale Suche
- [x] Feiertage (deutsche, bundesweit – ohne externe Abhängigkeit)
- [ ] Ferien / Müllkalender als kuratierte Kalender-Feeds
- [ ] Farbcodierung Termine ↔ Familienmitglied (Mapping-UI)

## Phase 2 – Erweiterung  ✅ weitgehend umgesetzt
- [x] Dokumente (Paperless: lesen + Suche)
- [x] Inventar (Homebox: lesen + Suche)
- [x] Fristen-/Kündigungserkennung in Dokumenten (Titel-Heuristik → Insights)
- [x] Paket-Carrier-Auto-Erkennung (DHL/DPD/GLS/Amazon/UPS) + Tracking-Links
- [x] Rezepte & Essensplanung (Wochenplan → automatische Einkaufsliste)
- [x] Finanzen (Daueraufträge/Versicherungen/Abos, monatliche Fixkosten)
- [x] Serien/Filme: Sonarr/Radarr (Demnächst, Download-Queue, Hinzufügen) – im Medien-Modul + per Chat/MCP steuerbar
- [x] Homelab-Status-Board (up/down + Links) für Dienste ohne tiefe Integration (SABnzbd, Immich, Trilium …)
- [ ] Paket-Status-Abruf via Carrier-API (statt manuell/Link)
- [ ] Fristen aus Paperless-Custom-Fields (statt Titel-Heuristik)

## Phase 3 – Intelligenz
- [x] Home Assistant (Übersicht + Steuerung)
- [x] Sprachsteuerung im AI-Panel (Web Speech API)
- [ ] Siri Shortcuts
- [ ] Automatische Terminplanung (freie Zeitfenster erkennen & vorschlagen)
- [ ] KI-Agenten mit Gedächtnis (RAG über Paperless/Notizen via Qdrant)
- [ ] Automationen („niemand zuhause → Alarm")

## Phase 4 – Familienwissen
- [x] Wartungspläne (Auto/Haus/Garten/Geräte, mit Fälligkeits-Reschedule)
- [ ] Reise-/Urlaubsplanung, Urlaubsmodus
- [ ] Gesundheitsübersicht, Haustiere
- [ ] Native Mobile-App (Widgets, Apple Watch, FaceID, Offline)

## Technische To-dos
- [x] Hintergrund-Scheduler für fällige Erinnerungen → automatischer Push
- [x] Test-Suite (pytest, 49 Tests)
- [x] Alembic-Migrationen (statt `create_all`, mit Bestandsschutz für bestehende DBs)
- [x] CI-Pipeline (GitHub Actions: Tests + Ruff)
- [ ] Optional: Authentik/OAuth2 & Passkeys statt lokalem Login
- [ ] Optional: Next.js/React-Frontend gegen die bestehende API
