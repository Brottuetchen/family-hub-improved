# NousResearch/hermes-agent als KI-Gehirn

Hermes Family OS nutzt den **echten** [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
als eigentliches KI-Gehirn – mit **allen** seinen Funktionen (Skills/Selbstlernen,
Memory, 40+ Tools, Subagents, Cron, Voice) und dessen **Abo-Logins** (u.a.
OpenAI **Codex „Sign in with ChatGPT"** und **Nous Portal**).

hermes-agent läuft **separat als Sidecar** und wird **über unser Interface** genutzt:
- **„Assistent"** (unsere UI): dünner Chat-Client mit Streaming + **Voice-Messages**,
  der ausschließlich den Sidecar anspricht. **Kein** eigener Agent, **kein**
  Wort-Matcher – ist kein Sidecar da, sagt der Chat das klar.
- **„Hermes Agent"** (eingebettet, optional): sein Web-Dashboard hinter unserem
  Login (`/agent/*`) – **falls** die gepinnte Version ein Dashboard mitbringt.

## Bestätigte Fakten (Upstream `main`)
- **OpenAI-kompatibler API-Server** (`gateway/platforms/api_server.py`):
  `POST /v1/chat/completions` (SSE-Streaming), `/v1/models`, `/v1/responses`, Sessions.
  Default **`127.0.0.1:8642`** → im Container `API_SERVER_HOST=0.0.0.0`,
  `API_SERVER_PORT=8642`; **Bearer-Auth** via `API_SERVER_KEY`.
- **Kein offizielles Docker-Image**, aber ein **Dockerfile** → wir **bauen aus dem Repo**.
  Daten/Config-Volume: **`/opt/data`** (`HERMES_HOME`), non-root User.
- **CLI**: `hermes setup` (Wizard), `hermes setup --portal` (Nous Portal),
  `hermes model` (Provider/Modell), `hermes mcp add …`, `hermes dashboard` (Web-UI).
- Der genaue **Server-Start-Befehl** ist versionsabhängig (`serve` vs. `gateway`) –
  im `docker-compose.yml` als `command:` gesetzt, ggf. anpassen.

## Architektur
```
PWA ─ „Assistent" (Chat/Voice) ─┐
    └ „Hermes Agent" (iframe) ───┤  (optional, falls Dashboard vorhanden)
                                 ▼
      unser FastAPI  ── relay /v1 + SSE ─▶  hermes-agent (Sidecar, :8642)
          │  /agent/* Reverse-Proxy (Auth)     • OpenAI-kompat. API (/v1/chat/completions)
          │                                    • Login: Codex/ChatGPT, Nous Portal
   hermes-mcp (MCP-Server) ◀── Tools ──────────┘  • Volume /opt/data (persistent)
     Einkauf/Kalender/Licht/Finanzen/…
```

## Einrichten (Docker)

**Am einfachsten:** `./install.sh` → „hermes-agent verbinden" **ja**. Der Installer
baut/startet den Sidecar und stößt `hermes setup` an. Manuell:

1. **Konfigurieren** (`.env`):
   ```env
   AI_PROVIDER=hermes_agent
   HERMES_AGENT_URL=http://hermes-agent:8642/v1
   HERMES_AGENT_TOKEN=<gleicher Wert wie API_SERVER_KEY>
   # HERMES_AGENT_DASHBOARD_URL=   # nur wenn die Version ein Web-Dashboard hat
   ```

2. **Version pinnen** in `docker-compose.yml` (Service `hermes-agent`):
   den Git-Ref `…hermes-agent.git#main` auf eine feste Version/Commit setzen.

3. **Bauen & starten** (großer Build, ~610 MB):
   ```bash
   docker compose --profile agent up -d --build
   ```

4. **Login/Setup (einmalig, interaktiv)** — deine Subskription:
   ```bash
   docker compose exec hermes-agent hermes setup            # Wizard (Codex/ChatGPT-Abo)
   docker compose exec hermes-agent hermes setup --portal   # ODER Nous Portal
   docker compose exec hermes-agent hermes model            # Provider/Modell wählen
   ```
   Die Anmeldung wird im Volume `hermes_agent_home` (`/opt/data`) persistiert.

Danach: **„Assistent"** nutzt hermes-agent (Chat + Voice).

## Voice-Messages
🎙 im „Assistent" nimmt Audio auf → `POST /api/ai/voice` → Transkription über den
Sidecar (`AI_TRANSCRIBE_MODEL`) → der Text läuft als normale Nachricht in den Chat.

## Haushalts-Werkzeuge steuern (MCP)
Damit hermes-agent **unsere Familien-Module** direkt bedienen kann (Einkauf,
Kalender, Smart Home, Finanzen, Wartung, Essensplan …), läuft der Dienst
**`hermes-mcp`** (`docker compose --profile agent up -d` startet ihn mit) und
exponiert unsere Werkzeuge als **MCP-Server** (Streamable HTTP) unter
`http://hermes-mcp:8765/mcp`.

In hermes-agent registrieren (einmalig):
```bash
docker compose exec hermes-agent hermes mcp add hermes-family \
  --url http://hermes-mcp:8765/mcp
```
(Der HTTP/Streamable-Transport wird aus der `--url` erkannt – ein `--transport`-Flag
gibt es in der gepinnten Agent-Version nicht.)

- Der Agent handelt mit der Rolle **`MCP_ROLE`** (Standard `partner`): dieselbe
  rollenbasierte Rechteprüfung wie im Chat (Kinder-Rolle darf z.B. kein Smart Home).
- Danach kann der Assistent Sätze wie „Setz Milch auf die Liste und mach das
  Licht im Wohnzimmer an" wirklich ausführen – über **unsere** Connectoren.

## Ehrliche Grenzen / Watch-outs
- **Kein offizielles Image** → Build aus dem Repo; **Version pinnen** (sehr aktiv).
- **Schwergewicht** (~610 MB Build) + eigener Dienst; braucht **Docker**.
- **Server-Start-Befehl versionsabhängig** (`command:` im Compose ggf. anpassen;
  `serve`/`gateway`). Prüfe, dass `:8642/v1/chat/completions` antwortet.
- **Login einmalig manuell** (Wizard/OAuth/Device-Code) — nicht vollständig headless.
- **Dashboard**: nur einbetten, wenn die gepinnte Version eines mitbringt
  (`hermes dashboard`); sonst `HERMES_AGENT_DASHBOARD_URL` leer lassen (der
  `/agent/*`-Proxy meldet dann sauber 503). **WebSocket/PTY** wird nicht geproxied.
- **Single-Profile:** zunächst ein gemeinsamer Familien-Assistent.

## Ohne Sidecar
Ist `AI_PROVIDER` nicht `hermes_agent` (oder der Sidecar nicht erreichbar), zeigt
der „Assistent" einen klaren **„nicht verbunden"**-Hinweis. Die App bleibt voll
nutzbar – nur der KI-Chat pausiert (kein Fake-Assistent).
