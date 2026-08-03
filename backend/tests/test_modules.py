"""Tests für die erweiterten Module (Rezepte, Essensplan, Finanzen, Wartung, Pakete)."""

from datetime import date


def test_recipes_and_meal_plan(client, auth):
    r = client.post(
        "/api/recipes",
        headers=auth,
        json={"title": "Spaghetti", "ingredients": ["500g Nudeln", "Tomaten"], "servings": 4},
    )
    assert r.status_code == 200
    recipe_id = r.json()["id"]
    assert r.json()["ingredients"] == ["500g Nudeln", "Tomaten"]

    today = date.today().isoformat()
    p = client.post("/api/meals/plan", headers=auth, json={"date": today, "recipe_id": recipe_id})
    assert p.status_code == 200

    plan = client.get("/api/meals/plan?days=7", headers=auth).json()
    assert any(e["title"] == "Spaghetti" for e in plan)

    # Einkaufsliste aus Plan (KitchenOwl nicht konfiguriert -> nur gesammelt)
    sl = client.post("/api/meals/shopping-list?days=7", headers=auth).json()
    assert "500g Nudeln" in sl["ingredients"]
    assert sl["added_to_kitchenowl"] == 0


def test_finance(client, auth):
    r = client.post(
        "/api/finance/expenses",
        headers=auth,
        json={"name": "Haftpflicht", "amount": 120.0, "interval": "yearly", "category": "insurance"},
    )
    assert r.status_code == 200
    client.post(
        "/api/finance/expenses",
        headers=auth,
        json={"name": "Streaming", "amount": 10.0, "interval": "monthly", "category": "subscription"},
    )
    ov = client.get("/api/finance/overview", headers=auth).json()
    # 120/12 + 10 = 20.0 monatlich
    assert ov["monthly_total"] == 20.0
    assert ov["by_category"]["subscription"] == 10.0


def test_maintenance_done_reschedules(client, auth):
    r = client.post(
        "/api/maintenance",
        headers=auth,
        json={"title": "Rauchmelder testen", "category": "home", "interval_days": 30},
    )
    assert r.status_code == 200
    tid = r.json()["id"]
    done = client.post(f"/api/maintenance/{tid}/done", headers=auth).json()
    assert done["last_done"] == date.today().isoformat()
    assert done["next_due"] is not None


def test_package_carrier_autodetect(client, auth):
    # Amazon-Muster TBA...
    r = client.post("/api/packages", headers=auth, json={"tracking_number": "TBA123456789000"})
    assert r.status_code == 200
    body = r.json()
    assert body["carrier"] == "amazon"
    assert body["tracking_url"] and "amazon" in body["tracking_url"]


def test_holidays_endpoint(client, auth):
    hol = client.get("/api/calendar/holidays?days=365", headers=auth).json()
    names = {h["name"] for h in hol}
    assert "Neujahr" in names or "1. Weihnachtstag" in names


def test_ai_finance_intent(client, auth):
    r = client.post("/api/ai/chat", headers=auth, json={"message": "Wie hoch sind unsere Fixkosten?"})
    assert r.status_code == 200
    assert "get_finance_overview" in r.json()["actions"]


def test_ai_meal_intent(client, auth):
    r = client.post("/api/ai/chat", headers=auth, json={"message": "Was gibts diese Woche zu essen?"})
    assert r.status_code == 200
    assert "get_meal_plan" in r.json()["actions"]


def test_dashboard_has_new_sections(client, auth):
    d = client.get("/api/dashboard", headers=auth).json()
    for key in ("holidays", "meals_today", "finance", "maintenance_due"):
        assert key in d
