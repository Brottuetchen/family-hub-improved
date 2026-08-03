"""Smoke-Tests für die Hermes-API."""


def test_health(client):
    data = client.get("/api/health").json()
    assert data["app"] == "Hermes Family OS"
    assert data["status"] == "online"


def test_protected_requires_auth(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/connectors").status_code == 401


def test_login_and_me(client, auth):
    me = client.get("/api/auth/me", headers=auth).json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"


def test_dashboard_shape(client, auth):
    d = client.get("/api/dashboard", headers=auth).json()
    for key in ("weather", "calendar", "tasks", "shopping", "reminders", "insights"):
        assert key in d


def test_connectors_registered(client, auth):
    conns = client.get("/api/connectors", headers=auth).json()
    names = {c["name"] for c in conns}
    assert {"weather", "caldav", "vikunja", "kitchenowl", "paperless", "homebox", "homeassistant"} <= names


def test_reminder_crud(client, auth):
    created = client.post("/api/reminders", headers=auth, json={"title": "Testerinnerung", "priority": "important"})
    assert created.status_code == 200
    rid = created.json()["id"]

    listed = client.get("/api/reminders", headers=auth).json()
    assert any(r["id"] == rid for r in listed)

    done = client.patch(f"/api/reminders/{rid}", headers=auth, json={"completed": True})
    assert done.status_code == 200 and done.json()["completed"] is True


def test_ai_rule_based_reminder(client, auth):
    r = client.post("/api/ai/chat", headers=auth, json={"message": "Erinnere mich heute Abend an den Müll"})
    assert r.status_code == 200
    body = r.json()
    assert body["used_llm"] is False
    assert "create_reminder" in body["actions"]


def test_ai_rule_based_shopping_intent(client, auth):
    # KitchenOwl nicht konfiguriert -> Tool wird gewählt, meldet aber sauber "nicht konfiguriert"
    r = client.post("/api/ai/chat", headers=auth, json={"message": "Bestell Milch"})
    assert r.status_code == 200
    assert "add_shopping_item" in r.json()["actions"]


def test_search_empty(client, auth):
    r = client.get("/api/search?q=irgendwas", headers=auth).json()
    assert r["count"] == 0 and r["results"] == []
