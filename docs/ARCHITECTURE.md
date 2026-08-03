# Architektur

Hermes ist als **intelligente Schicht** konzipiert, nicht als Ersatz für bestehende
Systeme. Die zentrale Idee: der Benutzer arbeitet nur mit Hermes, im Hintergrund
sprechen **Connectors** live mit den Fachsystemen.

## Schichten

```
┌──────────────────────────────────────────────────────────┐
│  Frontend (PWA)   – Dashboard, Module, Hermes-AI-Panel     │
├──────────────────────────────────────────────────────────┤
│  Router-Layer     – /api/dashboard, /api/tasks, /api/ai …  │
├──────────────────────────────────────────────────────────┤
│  Service-Layer    – notifications (Push), insights          │
│  AI-Layer         – llm · tools · agent                     │
├──────────────────────────────────────────────────────────┤
│  Connector-Layer  – base · registry · <system>_connector    │
├──────────────────────────────────────────────────────────┤
│  Fachsysteme      – Nextcloud, Vikunja, KitchenOwl, …       │
└──────────────────────────────────────────────────────────┘
        Hermes-eigener Speicher (DB): User, Family, Reminder, Package, PushSub
```

## Prinzipien

1. **Keine Datendoppelung.** Termine liegen in Nextcloud, Aufgaben in Vikunja usw.
   Hermes speichert selbst nur, was es zwingend besitzen muss (Nutzer/Rollen,
   Erinnerungen, Pakete, Push-Subscriptions).
2. **Graceful Degradation.** Jeder Connector meldet `is_configured`. Ohne
   Konfiguration liefert er leere Daten statt Fehler – die App bleibt nutzbar.
3. **Ausfalltoleranz.** Das Dashboard aggregiert alle Quellen *parallel*
   (`asyncio.gather`) und fängt Fehler pro Quelle ab. Ein hängendes Fachsystem
   legt nie das ganze Dashboard lahm.
4. **Frontend-agnostische API.** Alle Fähigkeiten sind REST-Endpunkte. Das
   mitgelieferte PWA-Frontend ist austauschbar (z.B. gegen Next.js).

## Request-Lebenszyklus (Beispiel Dashboard)

1. Frontend `GET /api/dashboard` mit Bearer-Token.
2. `routers/dashboard.py` prüft Auth (`get_current_user`).
3. Es ruft parallel Connectors (Wetter, Kalender, Aufgaben, Einkauf, Smart Home)
   und lokale Daten (Erinnerungen, Pakete) ab, plus `services/insights`.
4. Ergebnis wird zu einer einzigen, robusten JSON-Antwort zusammengesetzt.

## Hermes AI

- `ai/llm.py` – dünner OpenAI-kompatibler Client (funktioniert auch mit lokalen
  Modellen über `AI_BASE_URL`).
- `ai/tools.py` – Registry konkreter Werkzeuge, angebunden an Connectors & DB.
- `ai/agent.py` – Orchestrierung:
  - **LLM-Modus:** Function-Calling-Schleife (Tool-Aufrufe → Ergebnisse → Antwort).
  - **Fallback:** regelbasierte Intent-Erkennung (Deutsch), damit der Assistent
    auch ohne API-Key handlungsfähig ist.

## Datenmodell (Hermes-eigen)

| Modell               | Zweck                                            |
|----------------------|--------------------------------------------------|
| `User`               | Login, Rolle (admin/partner/kind/gast)           |
| `FamilyMember`       | Profil, Farbe, Avatar, Geburtstag                |
| `Reminder`           | Erinnerungen (auch KI-erzeugt)                   |
| `Package`            | Paket-Tracking                                   |
| `PushSubscriptionRecord` | Web-Push-Empfänger                           |
| `RefreshToken`, `LoginAttempt` | Session & Rate-Limiting                |

## Erweiterungspunkte

- **Neuer Connector** → siehe [`CONNECTORS.md`](CONNECTORS.md).
- **Neues KI-Werkzeug** → `Tool` in `ai/tools.py` registrieren.
- **Neues Modul-API** → Router unter `app/routers/` + in `app/main.py` einhängen.
