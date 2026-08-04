"""Tests für die wiederhergestellten Medien-Connectoren."""


def test_media_connectors_registered(client, auth):
    names = {c["name"] for c in client.get("/api/connectors", headers=auth).json()}
    assert {"plex", "audiobookshelf", "teddycloud", "overseerr"} <= names


def test_now_playing_graceful(client, auth):
    # Ohne Konfiguration: leere, aber valide Struktur (kein Fehler)
    r = client.get("/api/media/now-playing", headers=auth).json()
    assert r["count"] == 0 and r["streams"] == []


def test_requests_graceful(client, auth):
    assert client.get("/api/media/requests", headers=auth).json() == []


def test_dashboard_now_playing_field(client, auth):
    d = client.get("/api/dashboard", headers=auth).json()
    assert "now_playing" in d and isinstance(d["now_playing"], list)


