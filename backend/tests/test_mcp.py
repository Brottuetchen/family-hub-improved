"""Tests für den MCP-Server (Haushalts-Werkzeuge an hermes-agent)."""

import asyncio

from app.mcp.server import mcp


def test_mcp_lists_tools():
    tools = asyncio.run(mcp.list_tools())
    names = {t.name for t in tools}
    assert len(names) >= 20
    # zentrale Steuer- & Lese-Werkzeuge vorhanden
    assert {
        "add_shopping_item", "create_task", "create_reminder", "control_light",
        "add_expense", "get_daily_overview", "get_calendar", "search",
    } <= names


def test_mcp_tool_has_schema():
    tools = asyncio.run(mcp.list_tools())
    light = next(t for t in tools if t.name == "control_light")
    props = light.inputSchema.get("properties", {})
    assert "name" in props and "action" in props


def test_mcp_call_creates_reminder(client, auth):
    # Aufruf über MCP muss dieselbe DB treffen -> per API verifizierbar
    asyncio.run(mcp.call_tool("create_reminder", {"title": "MCP Erinnerung", "priority": "info"}))
    listed = client.get("/api/reminders?include_completed=true", headers=auth).json()
    assert any(r["title"] == "MCP Erinnerung" for r in listed)


def test_mcp_role_gating(monkeypatch):
    # Als Kind darf control_light (min_role partner) nicht ausgeführt werden.
    from app.config import settings

    monkeypatch.setattr(settings, "mcp_role", "child")
    res = asyncio.run(mcp.call_tool("control_light", {"name": "Wohnzimmer", "action": "on"}))
    text = str(res)
    assert "child" in text.lower() or "darf" in text.lower()
