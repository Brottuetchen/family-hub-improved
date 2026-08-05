"""Tests für die Admin-Verbindungsverwaltung (Laufzeit-Config im UI)."""

from app.config import settings
from app.core.database import SessionLocal
from app.models.config import ConfigOverride


def _cleanup():
    db = SessionLocal()
    try:
        db.query(ConfigOverride).delete()
        db.commit()
    finally:
        db.close()
    settings.vikunja_url = None
    settings.vikunja_token = None


def test_admin_settings_lists_connectors(client, auth):
    data = client.get("/api/admin/settings", headers=auth).json()
    names = {g["name"] for g in data}
    assert {"vikunja", "paperless", "sonarr", "hermes_agent"} <= names


def test_admin_settings_forbidden_for_child(client, auth):
    client.post("/api/auth/users", headers=auth,
                json={"username": "kidcfg", "email": "kc@t.de", "password": "kids1234", "role": "child"})
    tok = client.post("/api/auth/login", json={"username": "kidcfg", "password": "kids1234"}).json()["access_token"]
    r = client.get("/api/admin/settings", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_admin_update_applies_live_and_masks_secret(client, auth):
    try:
        r = client.put("/api/admin/settings", headers=auth,
                       json={"values": {"vikunja_url": "http://vik:3456", "vikunja_token": "tok-secret"}})
        assert r.status_code == 200
        # sofort auf settings angewandt (kein Neustart)
        assert settings.vikunja_url == "http://vik:3456"
        assert settings.vikunja_token == "tok-secret"
        # GET maskiert das Secret, liefert aber is_set + Klartext-URL
        vik = next(g for g in client.get("/api/admin/settings", headers=auth).json() if g["name"] == "vikunja")
        url_f = next(f for f in vik["fields"] if f["key"] == "vikunja_url")
        tok_f = next(f for f in vik["fields"] if f["key"] == "vikunja_token")
        assert url_f["value"] == "http://vik:3456"
        assert tok_f["value"] == "" and tok_f["is_set"] is True
        # leeres Secret bleibt erhalten
        client.put("/api/admin/settings", headers=auth, json={"values": {"vikunja_token": ""}})
        assert settings.vikunja_token == "tok-secret"
        # verschlüsselt in der DB (nicht im Klartext)
        db = SessionLocal()
        try:
            row = db.get(ConfigOverride, "vikunja_token")
            assert row is not None and row.secret is True and "tok-secret" not in row.value
        finally:
            db.close()
    finally:
        _cleanup()
