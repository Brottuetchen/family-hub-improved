# Hermes AI

Das **„Assistent"**-Chatfenster ist ein **dünner Client** zum echten
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), der
**separat als Sidecar** läuft. hermes ist der Agent – er bringt Skills,
Selbstlernen, Memory, 40+ Tools, Subagents, Cron und Voice mit und nutzt deine
**Abo-Logins** (Codex „Sign in with ChatGPT", Nous Portal). Wir **relayen** nur
Chat/Streaming/Voice und **betten** sein Voll-Dashboard ein.

> Es gibt in dieser App **keinen** eigenen Agenten und **keinen** Wort-Matcher.
> Ist kein Sidecar verbunden, sagt der Chat das klar – er erfindet keine Antwort.

## Einrichten (`AI_PROVIDER`)

Nur zwei sinnvolle Werte:

| Wert            | Verhalten |
|-----------------|-----------|
| `hermes_agent`  | **Empfohlen.** Chat/Voice sprechen den Sidecar an; er ist der Agent. |
| `none` / leer   | Chat inaktiv – klarer „nicht verbunden"-Hinweis statt Fake-Antwort. |

```env
AI_PROVIDER=hermes_agent
HERMES_AGENT_URL=http://hermes-agent:8890/v1
HERMES_AGENT_DASHBOARD_URL=http://hermes-agent:9119
HERMES_AGENT_MODEL=default
```
Am einfachsten über den Installer (`./install.sh` → „hermes-agent verbinden").
Starten & einloggen: **[docs/HERMES_AGENT.md](HERMES_AGENT.md)**.

## Chat-Oberfläche

Zwei Einstiegspunkte in unserem UI:
- **„Assistent"** – nativer Chat mit **Streaming** (SSE `/api/ai/stream`) und
  **Voice-Messages** (🎙 → `/api/ai/voice` → Transkription über den Sidecar).
  Der Verlauf wird **pro Nutzer serverseitig** gespeichert (`/api/ai/history`).
- **„Hermes Agent"** – sein **komplettes Web-Dashboard**, hinter unserem Login
  eingebettet (`/agent/*`): alle übrigen Funktionen (Skills, Memory, Subagents,
  Tool-/MCP-Verwaltung, Cron …).

## Unsere Module steuern (MCP)

Damit hermes **unsere** Familien-Module bedienen kann (Einkauf, Kalender, Licht,
Finanzen, Wartung, Essensplan …), läuft der Dienst **`hermes-mcp`** und exponiert
unsere Haushalts-Werkzeuge als **MCP-Server** (`http://hermes-mcp:8765/mcp`).
`docker compose --profile agent up -d` startet ihn mit.

- `/api/ai/tools` zeigt, welche Werkzeuge für deine Rolle steuerbar sind.
- Die Rolle, mit der der Agent handelt, setzt `MCP_ROLE` (Standard `partner`;
  `guest < child < partner < admin`) – dieselbe rollenbasierte Rechteprüfung.

Einrichtung des MCP-Servers in hermes-agent: **[docs/HERMES_AGENT.md](HERMES_AGENT.md)**.

## Beispiele (werden von hermes ausgeführt)

```
„Setz Milch auf die Liste und mach das Wohnzimmerlicht an"
„Erinnere mich jeden Dienstag 19 Uhr an den Müll"
„Plane Spaghetti für morgen und erzeuge die Einkaufsliste"
„Was steht heute an?"
```
Was möglich ist, bestimmt der hermes-agent (seine Tools + unsere MCP-Werkzeuge),
nicht diese App.
