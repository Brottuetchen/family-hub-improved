# Hermes AI

Der Assistent ist **werkzeugbasiert**: Er beantwortet nicht nur Fragen, sondern
führt Aktionen über die Module wirklich aus (Function Calling). „Hermes" ist der
**Name des Assistenten** – nicht zwingend das Modell. Welches Modell (falls
überhaupt) rechnet, bestimmt `AI_PROVIDER`.

## Betriebsmodi (`AI_PROVIDER`)

| Modus    | Was passiert | Voraussetzung |
|----------|--------------|---------------|
| `none`   | **Kein LLM.** Deutscher Regel-/Intent-Parser ordnet Sätze den Werkzeugen zu. Offline, sofort, deterministisch. | – |
| `local`  | Lokales, OpenAI-kompatibles Modell (Ollama, LM Studio, vLLM). Privat, kein Cloud-Traffic. | lokaler LLM-Server |
| `openai` | OpenAI-Cloud. | API-Key |

Im `none`-Modus „denkt" nichts im Hintergrund – der Chat ist reines
Request/Response. Dauerhaft läuft nur der Erinnerungs-Scheduler.

## Nous Hermes lokal betreiben (empfohlen fürs Homelab)

Mit dem optionalen Ollama-Dienst aus `docker-compose.yml`:

```bash
docker compose --profile ai up -d          # startet Ollama mit
docker compose exec ollama ollama pull hermes3   # Nous Hermes 3 laden
```

`.env`:
```env
AI_PROVIDER=local
AI_BASE_URL=http://ollama:11434/v1
AI_MODEL=hermes3
```
Neustart: `docker compose up -d`. Alternativen zu `hermes3`: `qwen2.5`, `llama3.1`
– alle mit Tool-/Function-Calling.

## Nutzerbezogen & rollenbasiert

- Der Assistent kennt den **angemeldeten Nutzer** (Name + Rolle) und personalisiert
  Antworten; neu erstellte Einträge (Erinnerungen etc.) gehören dieser Person.
- **Rollen-Rechte:** Jedes Werkzeug hat eine Mindest-Rolle
  (`guest < child < partner < admin`). Kinder können z.B. Einkäufe/Erinnerungen
  anlegen, aber **nicht** das Smart Home steuern oder Finanzen ändern. Die
  erlaubten Werkzeuge werden dem Modell rollenabhängig angeboten **und** bei der
  Ausführung serverseitig geprüft (`/api/ai/tools` zeigt die für dich erlaubten).

## Werkzeuge (Auszug)

Lesen: `get_daily_overview`, `get_weather`, `get_calendar`, `list_tasks`,
`get_shopping_list`, `get_finance_overview`, `get_meal_plan`, `get_now_playing`,
`get_maintenance`, `list_family`, `list_packages`, `get_requests`, `search`.

Steuern: `add_shopping_item`, `create_task`, `create_reminder` (inkl.
Wiederholung), `add_package`, `add_meal`, `generate_shopping_list`
(child+); `control_light`, `add_expense`, `complete_maintenance` (partner+).

## Beispiele

```
„Was steht heute an?"                      → Tagesübersicht
„Bestell Milch"                            → Einkaufsliste
„Erinnere mich jeden Dienstag 19 Uhr an den Müll" → wiederkehrende Erinnerung
„Mach das Licht im Wohnzimmer an"          → Smart Home (ab Rolle partner)
„Was läuft gerade?"                        → Plex/Hörbücher/Tonies
„Plane Spaghetti für morgen"               → Essensplan
```
