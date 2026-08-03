"""Tests für die rollenbasierten Haushalts-Werkzeuge (via MCP an hermes-agent).

Der Chat selbst ist ein reiner hermes-agent-Relay (kein Wort-Matcher, kein
eigener Agent) – die eigentliche Ausführung/Steuerung läuft über die Tool-
Registry (MCP). Rollen-Gating wird in test_mcp.py end-to-end geprüft.
"""

from app.ai.tools import TOOLS, is_allowed


def test_new_control_tools_registered():
    expected = {
        "get_calendar", "get_smart_home", "control_light", "add_package", "list_packages",
        "add_expense", "get_maintenance", "complete_maintenance", "add_meal",
        "generate_shopping_list", "list_family", "get_requests",
    }
    assert expected <= set(TOOLS.keys())


def test_role_levels():
    assert is_allowed("partner", "admin") is True
    assert is_allowed("partner", "child") is False
    assert is_allowed("guest", "child") is True


def test_ai_status_is_role_aware(client, auth):
    s = client.get("/api/ai/status", headers=auth).json()
    assert s["role"] == "admin"
    assert s["tool_count"] >= 15  # Admin sieht alle Werkzeuge


def _make_child_and_login(client, auth):
    client.post(
        "/api/auth/users",
        headers=auth,
        json={"username": "kind1", "email": "kind1@test.de", "password": "kids1234", "role": "child"},
    )
    return client.post("/api/auth/login", json={"username": "kind1", "password": "kids1234"}).json()["access_token"]


def test_child_tool_list_smaller(client, auth):
    token = _make_child_and_login(client, auth)
    child_tools = client.get("/api/ai/tools", headers={"Authorization": f"Bearer {token}"}).json()
    names = {t["name"] for t in child_tools}
    assert "control_light" not in names  # partner-only
    assert "add_shopping_item" in names  # erlaubt
