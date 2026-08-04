"""Tests für Sonarr/Radarr-Connectoren, Media-Endpunkte und Homelab-Board."""

import asyncio

from app.config import settings
from app.connectors.registry import registry
from app.connectors.sonarr_connector import _progress


def test_arr_connectors_registered():
    assert registry.get("sonarr") is not None
    assert registry.get("radarr") is not None


def test_arr_graceful_without_config():
    # Ohne Konfiguration: keine Fehler, leere Ergebnisse (graceful degradation).
    for key in ("sonarr", "radarr"):
        c = registry.get(key)
        assert c.is_configured is False
        assert asyncio.run(c.get_upcoming()) == []
        assert asyncio.run(c.get_queue()) == []
        assert asyncio.run(c.add("whatever")) is None


def test_progress_math():
    assert _progress({"size": 100, "sizeleft": 25}) == 75
    assert _progress({"size": 0, "sizeleft": 0}) == 0
    assert _progress({}) == 0


def test_media_upcoming_queue_endpoints(client, auth):
    assert client.get("/api/media/upcoming", headers=auth).status_code == 200
    assert client.get("/api/media/queue", headers=auth).json() == []


def test_add_media_role_gate(client, auth):
    # Admin: Rolle passiert -> 503 (Sonarr nicht konfiguriert), NICHT 403.
    r = client.post("/api/media/series", headers=auth, json={"query": "The Bear"})
    assert r.status_code == 503
    # Kind: 403 (Rolle unzureichend, partner+ nötig).
    client.post("/api/auth/users", headers=auth,
                json={"username": "kidm", "email": "kidm@t.de", "password": "kids1234", "role": "child"})
    tok = client.post("/api/auth/login", json={"username": "kidm", "password": "kids1234"}).json()["access_token"]
    r2 = client.post("/api/media/movie", headers={"Authorization": f"Bearer {tok}"}, json={"query": "Dune"})
    assert r2.status_code == 403


def test_homelab_board_empty_by_default(client, auth):
    assert client.get("/api/connectors/services", headers=auth).json() == []


def test_homelab_service_list_parsing(monkeypatch):
    monkeypatch.setattr(
        settings, "homelab_services",
        '[{"name":"SAB","url":"http://x:8080","category":"a","icon":"📥"},{"bad":"no url"}]',
    )
    lst = settings.homelab_service_list
    assert len(lst) == 1  # der unvollständige Eintrag wird verworfen
    assert lst[0]["name"] == "SAB" and lst[0]["url"] == "http://x:8080"


def test_mcp_has_arr_tools():
    from app.mcp.server import mcp

    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert {"get_upcoming_media", "get_download_queue", "add_series", "add_movie"} <= names
