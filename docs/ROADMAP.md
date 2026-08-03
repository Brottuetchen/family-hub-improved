# Roadmap

Die Vision umfasst vier Phasen. Der aktuelle Stand ist das **Phase-1-MVP-Fundament**
inklusive Connector-Architektur und Hermes AI.

## Phase 1 – Kern (MVP)  ✅ weitgehend umgesetzt
- [x] Login & Rollen (admin/partner/kind/gast)
- [x] Dashboard (aggregierte Tagesübersicht)
- [x] Kalender-Connector (CalDAV/Nextcloud)
- [x] Aufgaben (Vikunja: lesen + anlegen)
- [x] Einkauf (KitchenOwl: lesen + hinzufügen)
- [x] Erinnerungen & Pakete (Hermes-eigen)
- [x] Wetter (Open-Meteo)
- [x] Push (Web Push / VAPID)
- [x] Hermes AI (Tools + Fallback)
- [x] Globale Suche
- [ ] Feiertage / Ferien / Müllkalender als kuratierte Kalender-Feeds
- [ ] Farbcodierung Termine ↔ Familienmitglied (Mapping-UI)

## Phase 2 – Erweiterung
- [x] Dokumente (Paperless) – Grundgerüst
- [x] Inventar (Homebox) – Grundgerüst
- [ ] Fristen-/Kündigungserkennung in Dokumenten (Tags/Custom Fields, Push)
- [ ] Paket-Auto-Erkennung (DHL/DPD/GLS/Amazon via Mail/API statt manuell)
- [ ] Rezepte & Essensplanung (Wochenplan → automatische Einkaufsliste)
- [ ] Finanzen (laufende Kosten, Daueraufträge, Budgets)

## Phase 3 – Intelligenz
- [x] Home Assistant (Übersicht + Steuerung) – Grundgerüst
- [ ] Sprachsteuerung (Siri Shortcuts, Web Speech API)
- [ ] Automatische Terminplanung (freie Zeitfenster erkennen & vorschlagen)
- [ ] KI-Agenten mit Gedächtnis (RAG über Paperless/Notizen via Qdrant)
- [ ] Automationen („niemand zuhause → Alarm")

## Phase 4 – Familienwissen
- [ ] Reise-/Urlaubsplanung, Urlaubsmodus
- [ ] Gesundheitsübersicht, Haustiere, Wartungspläne
- [ ] Native Mobile-App (Widgets, Apple Watch, FaceID, Offline)

## Technische To-dos
- [ ] Alembic-Migrationen (statt `create_all`)
- [ ] Test-Suite ausbauen (pytest) & CI
- [ ] Hintergrund-Scheduler für fällige Erinnerungen → automatischer Push
- [ ] Optional: Authentik/OAuth2 & Passkeys statt lokalem Login
- [ ] Optional: Next.js/React-Frontend gegen die bestehende API
