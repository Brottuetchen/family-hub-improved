"""Tests für den Installer (Setup-Assistent)."""

import builtins
import getpass

import scripts.setup as setup
from scripts.setup import CONNECTORS, load_env, write_env


def test_env_roundtrip(tmp_path):
    p = tmp_path / ".env"
    env = {
        "SECRET_KEY": "abc123",
        "AI_PROVIDER": "openai",
        "AI_API_KEY": "sk-xyz",
        "VIKUNJA_URL": "https://vikunja.example.com",
        "CUSTOM_EXTRA": "keepme",
    }
    write_env(p, env)
    loaded = load_env(p)
    assert loaded["SECRET_KEY"] == "abc123"
    assert loaded["AI_PROVIDER"] == "openai"
    assert loaded["AI_API_KEY"] == "sk-xyz"
    assert loaded["VIKUNJA_URL"] == "https://vikunja.example.com"
    # Nicht vordefinierte Keys bleiben erhalten
    assert loaded["CUSTOM_EXTRA"] == "keepme"


def test_env_backup_created(tmp_path):
    p = tmp_path / ".env"
    p.write_text("SECRET_KEY=old\n", encoding="utf-8")
    write_env(p, {"SECRET_KEY": "new"})
    assert (tmp_path / ".env.bak").exists()
    assert "old" in (tmp_path / ".env.bak").read_text()
    assert load_env(p)["SECRET_KEY"] == "new"


def test_connectors_cover_all_systems():
    keys = {k for _, fields in CONNECTORS for (k, _, _) in fields}
    expected = {
        "CALDAV_URL", "CALDAV_USERNAME", "CALDAV_PASSWORD",
        "VIKUNJA_TOKEN", "KITCHENOWL_TOKEN", "PAPERLESS_TOKEN", "HOMEBOX_TOKEN",
        "HOMEASSISTANT_TOKEN", "PLEX_TOKEN", "AUDIOBOOKSHELF_TOKEN",
        "TEDDYCLOUD_URL", "OVERSEERR_API_KEY",
    }
    assert expected <= keys


def _run_setup(monkeypatch, tmp_path, target):
    """Führt den Assistenten mit Default-Antworten aus und liefert die .env-Werte."""
    env_path = tmp_path / ".env"
    monkeypatch.setattr(setup, "ENV_PATH", env_path)
    monkeypatch.setenv("HERMES_INSTALL_TARGET", target)
    # Alle Eingaben = Enter (Vorgaben übernehmen); VAPID überspringen.
    monkeypatch.setattr(builtins, "input", lambda *a, **k: "")
    monkeypatch.setattr(getpass, "getpass", lambda *a, **k: "")
    monkeypatch.setattr(setup, "gen_vapid", lambda: ("", ""))
    assert setup.main() == 0
    return load_env(env_path)


def test_local_install_uses_sqlite_not_docker_host(monkeypatch, tmp_path):
    # Regression: lokal darf NICHT den Compose-Host 'db' verwenden.
    env = _run_setup(monkeypatch, tmp_path, "local")
    assert env["DATABASE_URL"] == "sqlite:///./hermes.db"
    assert "@db:" not in env["DATABASE_URL"]


def test_docker_install_defaults_to_sqlite(monkeypatch, tmp_path):
    # Docker-Ziel ohne Postgres-Zusage -> ebenfalls SQLite (kein 'db'-Host).
    env = _run_setup(monkeypatch, tmp_path, "docker")
    assert env["DATABASE_URL"] == "sqlite:///./hermes.db"
