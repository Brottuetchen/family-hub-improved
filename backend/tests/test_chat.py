"""Tests für Chat-Verlauf, Streaming und den Hermes-Tool-Call-Parser."""

from app.ai.agent import _parse_text_tool_calls


def test_text_tool_call_parser_tags():
    content = 'Klar. <tool_call>{"name": "add_shopping_item", "arguments": {"name": "Milch"}}</tool_call>'
    calls = _parse_text_tool_calls(content)
    assert calls == [{"name": "add_shopping_item", "arguments": {"name": "Milch"}}]


def test_text_tool_call_parser_bare_json():
    content = '{"name": "get_weather", "arguments": {}}'
    calls = _parse_text_tool_calls(content)
    assert calls and calls[0]["name"] == "get_weather"


def test_text_tool_call_parser_none():
    assert _parse_text_tool_calls("Einfach nur Text ohne Werkzeug.") == []


def test_chat_history_persists(client, auth):
    client.delete("/api/ai/history", headers=auth)  # deterministischer Start
    client.post("/api/ai/chat", headers=auth, json={"message": "Was steht heute an?"})
    client.post("/api/ai/chat", headers=auth, json={"message": "Und das Wetter?"})
    hist = client.get("/api/ai/history", headers=auth).json()
    roles = [m["role"] for m in hist]
    assert roles.count("user") == 2 and roles.count("assistant") == 2
    assert hist[0]["content"] == "Was steht heute an?"


def test_chat_history_clear(client, auth):
    client.post("/api/ai/chat", headers=auth, json={"message": "Hallo"})
    assert client.delete("/api/ai/history", headers=auth).json()["cleared"] >= 1
    assert client.get("/api/ai/history", headers=auth).json() == []


def test_stream_endpoint(client, auth):
    resp = client.post("/api/ai/stream", headers=auth, json={"message": "Was steht heute an?"})
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")
    body = resp.text
    assert "data:" in body
    assert '"type": "delta"' in body or '"type":"delta"' in body
    assert "done" in body
