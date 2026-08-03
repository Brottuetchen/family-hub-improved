# NousResearch/hermes-agent als KI-Gehirn

Hermes Family OS kann den **kompletten** [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent)
als eigentliches KI-Gehirn nutzen — mit **allen** seinen Funktionen (Skills/Selbstlernen,
Memory, 40+ Tools, Subagents, Cron, Voice) und dessen **Abo-Logins** (u.a.
OpenAI **Codex „Sign in with ChatGPT"** und **Nous Portal**).

hermes-agent läuft **separat als Sidecar** und wird **über unser Interface** genutzt:
- **„Assistent"** (nativ, unsere UI): Chat mit Streaming + **Voice-Messages**.
- **„Hermes Agent"** (eingebettet): sein komplettes Web-Dashboard hinter unserem
  Login (`/agent/*`) — für alle übrigen Funktionen.

## Architektur
```
PWA ─ „Assistent" (Chat/Voice) ─┐
    └ „Hermes Agent" (iframe) ───┤
                                 ▼
      unser FastAPI  ── relay /v1 + SSE ─▶  hermes-agent (Sidecar)
          │  /agent/* Reverse-Proxy (Auth)     • OpenAI-kompat. API + Dashboard
          │                                    • Login: Codex/ChatGPT, Nous Portal
   hermes-mcp (MCP-Server) ◀── Tools ──────────┘  • Volume ~/.hermes (persistent)
     Einkauf/Kalender/Licht/Finanzen/…
```

## Einrichten (Docker)

1. **Konfigurieren** (Installer oder `.env`):
   ```env
   AI_PROVIDER=hermes_agent
   HERMES_AGENT_URL=http://hermes-agent:8890/v1
   HERMES_AGENT_DASHBOARD_URL=http://hermes-agent:9119
   HERMES_AGENT_MODEL=default
   HERMES_AGENT_IMAGE=nousresearch/hermes-agent:<GEPINNTE_VERSION>
   ```
   > **Pinne eine feste Version!** hermes-agent ist groß (~610 MB) und sehr aktiv.
   > Prüfe Image-Name, Start-Befehl und Ports gegen die von dir gepinnte Release
   > (`docker-compose.yml` enthält dazu Kommentare; ggf. `image:` durch `build:` ersetzen).

2. **Starten:**
   ```bash
   docker compose --profile agent up -d
   ```

3. **Login (einmalig, interaktiv)** — deine Subskription:
   ```bash
   # OpenAI Codex / „Sign in with ChatGPT" (Abo)
   docker compose exec hermes-agent hermes auth add openai --type device-code
   # ODER Nous Portal (1 Abo, 300+ Modelle)
   docker compose exec hermes-agent hermes setup --portal
   # ODER vorhandenes Codex-Login importieren: ~/.codex/auth.json in das Volume legen
   ```
   Die Anmeldung wird im Volume `hermes_agent_home` (`~/.hermes/auth.json`) persistiert.

Danach: **„Assistent"** nutzt hermes-agent (Chat + Voice), **„Hermes Agent"**
zeigt sein volles Dashboard.

## Voice-Messages
🎙 im „Assistent" nimmt Audio auf → `POST /api/ai/voice` → Transkription über den
Sidecar/`AI_TRANSCRIBE_MODEL` → der Text läuft als normale Nachricht in den Chat.

## Haushalts-Werkzeuge steuern (MCP)
Damit hermes-agent **unsere Familien-Module** direkt bedienen kann (Einkauf,
Kalender, Smart Home, Finanzen, Wartung, Essensplan …), läuft der Dienst
**`hermes-mcp`** (`docker compose --profile agent up -d` startet ihn mit) und
exponiert unsere 23 Werkzeuge als **MCP-Server** (Streamable HTTP) unter
`http://hermes-mcp:8765/mcp`.

In hermes-agent einen MCP-Server hinzufügen, der dorthin zeigt, z.B.:
```bash
docker compose exec hermes-agent hermes mcp add hermes-family \
  --transport streamable-http --url http://hermes-mcp:8765/mcp
```
(exakter Befehl je nach gepinnter hermes-agent-Version – siehe dessen `hermes mcp`-Hilfe).

- Der Agent handelt mit der Rolle **`MCP_ROLE`** (Standard `partner`): dieselbe
  rollenbasierte Rechteprüfung wie im Chat (Kinder-Rolle darf z.B. kein Smart Home).
- Danach kann der Assistent Sätze wie „Setz Milch auf die Liste und mach das
  Licht im Wohnzimmer an" wirklich ausführen – über **unsere** Connectoren.

## Ehrliche Grenzen / Watch-outs
- **Schwergewicht** (~610 MB) + eigener Dienst; **Version pinnen**.
- **Login ist einmalig manuell** (Device-Code/OAuth) — nicht vollständig headless.
- **Single-Profile:** zunächst ein gemeinsamer Familien-Assistent
  (pro-Nutzer via `?profile=<name>` als Folgeschritt).
- **Reverse-Proxy `/agent/*`** reicht HTTP durch und erlaubt die Einbettung
  (X-Frame-Options entfernt, same-origin). **WebSocket** (Dashboard-PTY) wird in
  v1 **nicht** geproxied. Falls das Dashboard Asset-Pfad-Rewrites braucht, hinter
  einem Pfad-Präfix betreiben oder Traefik/NPM vorschalten.
- **Nicht multi-tenant** out-of-the-box.

## Ohne Sidecar
Ist `AI_PROVIDER` nicht `hermes_agent`, nutzt der „Assistent" das konfigurierte
Cloud-/Lokalmodell **oder** den regelbasierten Fallback — die App bleibt voll nutzbar.
