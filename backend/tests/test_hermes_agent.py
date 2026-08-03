"""Tests für den hermes-agent-Relay-Modus (ohne echten Sidecar – Mock)."""

from app.ai.llm import llm_client
from app.config import settings


def test_agentic_flags(monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "hermes_agent")
    monkeypatch.setattr(settings, "hermes_agent_url", "http://hermes-agent:8890/v1")
    assert llm_client.is_agentic is True
    assert llm_client.is_configured is True
    monkeypatch.setattr(settings, "hermes_agent_url", None)
    assert llm_client.is_agentic is True
    assert llm_client.is_configured is False  # ohne URL nicht konfiguriert


def test_status_reports_hermes_agent(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "hermes_agent")
    monkeypatch.setattr(settings, "hermes_agent_url", "http://hermes-agent:8890/v1")
    monkeypatch.setattr(settings, "hermes_agent_model", "hermes-4")
    st = client.get("/api/ai/status", headers=auth).json()
    assert st["mode"] == "hermes-agent"
    assert st["agentic"] is True
    assert st["model"] == "hermes-4"


def test_chat_relays_to_sidecar(client, auth, monkeypatch):
    async def fake_chat(messages, tools=None, tool_choice="auto"):
        # Relay darf KEINE Tools injizieren – der Sidecar ist der Agent.
        assert tools is None
        return {"content": "Antwort vom Sidecar"}

    monkeypatch.setattr(settings, "ai_provider", "hermes_agent")
    monkeypatch.setattr(settings, "hermes_agent_url", "http://hermes-agent:8890/v1")
    monkeypatch.setattr(llm_client, "chat", fake_chat)

    r = client.post("/api/ai/chat", headers=auth, json={"message": "Hallo"}).json()
    assert r["reply"] == "Antwort vom Sidecar"
    assert r["used_llm"] is True
    assert r["actions"] == []


def test_agent_proxy_requires_auth(client):
    # Kein Login -> weder Bearer noch Cookie -> 401
    r = client.get("/agent/")
    assert r.status_code == 401


def test_agent_proxy_cookie_auth(client, auth, monkeypatch):
    # 'auth'-Fixture hat eingeloggt -> access_token-Cookie ist gesetzt.
    # Ohne Dashboard-URL -> 503 (nicht 401) beweist: Cookie-Auth hat gegriffen.
    monkeypatch.setattr(settings, "hermes_agent_dashboard_url", None)
    r = client.get("/agent/")  # bewusst ohne Authorization-Header
    assert r.status_code == 503


def test_voice_transcription(client, auth, monkeypatch):
    async def fake_transcribe(content, filename, content_type):
        assert content  # Audio-Bytes kamen an
        return "Bestell Milch"

    monkeypatch.setattr(settings, "ai_provider", "hermes_agent")
    monkeypatch.setattr(settings, "hermes_agent_url", "http://hermes-agent:8890/v1")
    monkeypatch.setattr(llm_client, "transcribe", fake_transcribe)

    files = {"audio": ("voice.webm", b"RIFF...fake-audio...", "audio/webm")}
    r = client.post("/api/ai/voice", headers=auth, files=files)
    assert r.status_code == 200
    assert r.json()["text"] == "Bestell Milch"


def test_voice_requires_backend(client, auth, monkeypatch):
    monkeypatch.setattr(settings, "ai_provider", "none")
    files = {"audio": ("voice.webm", b"x", "audio/webm")}
    r = client.post("/api/ai/voice", headers=auth, files=files)
    assert r.status_code == 501


def test_stream_relays_tokens(client, auth, monkeypatch):
    async def fake_stream(messages):
        for token in ["Hallo", " von", " Hermes", " Agent"]:
            yield token

    monkeypatch.setattr(settings, "ai_provider", "hermes_agent")
    monkeypatch.setattr(settings, "hermes_agent_url", "http://hermes-agent:8890/v1")
    monkeypatch.setattr(llm_client, "stream_chat", fake_stream)

    client.delete("/api/ai/history", headers=auth)
    resp = client.post("/api/ai/stream", headers=auth, json={"message": "Hi"})
    assert resp.status_code == 200
    body = resp.text
    assert "Hermes" in body and "Agent" in body
    assert "done" in body
    # Verlauf enthält die zusammengesetzte Antwort
    hist = client.get("/api/ai/history", headers=auth).json()
    assert any("Hermes Agent" in m["content"] for m in hist if m["role"] == "assistant")
