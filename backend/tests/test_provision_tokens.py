"""Tests für die vollautomatische Token-Provisionierung (offline, ohne Netzwerk).

Der HTTP-Layer wird durch ein Fake ersetzt; getestet werden die .env-Upsert-Logik,
die pro-Dienst-Flows (inkl. der kniffligen Homebox-"Bearer"-Prefix-Behandlung und
der Vikunja-Permissions-Umwandlung) sowie Idempotenz/--force in main().
"""

import importlib.util
import json
from pathlib import Path

import pytest

# Standalone-Skript per Pfad laden (unabhängig vom cwd der Testausführung).
_SPEC = importlib.util.spec_from_file_location(
    "provision_tokens", Path(__file__).resolve().parents[1] / "scripts" / "provision_tokens.py"
)
prov = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(prov)


# --------------------------------------------------------------------------- #
# .env Upsert
# --------------------------------------------------------------------------- #
def test_env_upsert_updates_in_place_and_appends(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# Kopf\nCOMPOSE_PROFILES=vikunja,homebox\nFOO=bar\n# Kommentar\nKEEP=1\n")
    prov.upsert_env({"FOO": "baz", "VIKUNJA_TOKEN": "tk_neu"}, path=env)
    data = prov.read_env(env)
    text = env.read_text()

    assert data["FOO"] == "baz"                 # bestehender Key ersetzt
    assert data["VIKUNJA_TOKEN"] == "tk_neu"    # neuer Key angehängt
    assert data["KEEP"] == "1"                  # unberührt
    assert text.startswith("# Kopf")            # führender Kommentar erhalten
    assert "# Kommentar" in text                # Inline-Kommentar erhalten


def test_env_upsert_value_may_contain_equals(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A=1\n")
    prov.upsert_env({"TOK": "abc==def=="}, path=env)   # base64-artige Werte mit '='
    assert prov.read_env(env)["TOK"] == "abc==def=="


def test_env_upsert_creates_file_when_missing(tmp_path):
    env = tmp_path / ".env"
    prov.upsert_env({"X": "y"}, path=env)
    assert prov.read_env(env)["X"] == "y"


# --------------------------------------------------------------------------- #
# Fake-HTTP-Gerüst
# --------------------------------------------------------------------------- #
def _fake_http(routes):
    """Baut ein http-Ersatz-Callable aus {url_suffix: (status, json_or_None)}."""
    seen = []

    def _http(method, url, *, headers=None, data=None, form=None, timeout=20):
        seen.append((method, url, data or form, headers))
        for suffix, (status, payload) in routes.items():
            if url.endswith(suffix):
                body = json.dumps(payload) if payload is not None else ""
                return prov.Resp(status, body)
        return prov.Resp(404, "")

    _http.seen = seen
    return _http


# --------------------------------------------------------------------------- #
# Pro-Dienst-Flows
# --------------------------------------------------------------------------- #
def test_homebox_strips_bearer_prefix(monkeypatch):
    # Homebox liefert token bereits mit "Bearer "-Prefix – der Connector setzt selbst
    # "Bearer " davor. Ohne Strippen entstünde "Bearer Bearer ..." (401). Regressionsschutz.
    monkeypatch.setattr(prov, "http", _fake_http({
        "/api/v1/users/register": (204, None),
        "/api/v1/users/login": (200, {"token": "Bearer eyJraw", "expiresAt": "x"}),
    }))
    tok, note = prov.prov_homebox("http://h:7745", "a@b.c", "pw")
    assert tok == "eyJraw"          # Prefix entfernt
    assert not tok.lower().startswith("bearer")


def test_vikunja_creates_permanent_token_with_flattened_perms(monkeypatch):
    fake = _fake_http({
        "/api/v1/register": (201, None),
        "/api/v1/login": (200, {"token": "jwt"}),
        "/api/v1/routes": (200, {"tasks": {"read_all": {}, "update": {}}, "projects": {"read_all": {}}}),
        "/api/v1/tokens": (200, {"token": "tk_PERM"}),
    })
    monkeypatch.setattr(prov, "http", fake)
    tok, note = prov.prov_vikunja("http://h:3456", "u", "e@x.y", "pw")
    assert tok == "tk_PERM"
    # /routes (Gruppe→dict) wurde zu Gruppe→Liste flach gemacht
    put = next(c for c in fake.seen if c[0] == "PUT" and c[1].endswith("/api/v1/tokens"))
    assert put[2]["permissions"]["tasks"] == ["read_all", "update"]
    assert "expires_at" in put[2]


def test_vikunja_falls_back_to_long_jwt_when_token_endpoint_missing(monkeypatch):
    calls = {"n": 0}

    def _http(method, url, *, headers=None, data=None, form=None, timeout=20):
        if url.endswith("/api/v1/register"):
            return prov.Resp(201, "")
        if url.endswith("/api/v1/login"):
            calls["n"] += 1
            # erster Login = kurzes JWT, zweiter (long_token) = langlebiges JWT
            return prov.Resp(200, json.dumps({"token": "jwt-long" if data.get("long_token") else "jwt-short"}))
        if url.endswith("/api/v1/routes"):
            return prov.Resp(404, "")            # kein API-Token-Feature
        if url.endswith("/api/v1/tokens"):
            return prov.Resp(404, "")
        return prov.Resp(404, "")

    monkeypatch.setattr(prov, "http", _http)
    tok, note = prov.prov_vikunja("http://h:3456", "u", "e@x.y", "pw")
    assert tok == "jwt-long"
    assert "30" in note or "langlebig" in note.lower()


def test_kitchenowl_signup_then_longlived(monkeypatch):
    fake = _fake_http({
        "/api/auth/signup": (200, {"access_token": "acc"}),
        "/api/auth/llt": (200, {"longlived_token": "llt_TOKEN"}),
    })
    monkeypatch.setattr(prov, "http", fake)
    tok, note = prov.prov_kitchenowl("http://h:8082", "u", "Name", "pw")
    assert tok == "llt_TOKEN"
    # LLT-Aufruf muss den access_token als Bearer tragen
    llt = next(c for c in fake.seen if c[1].endswith("/api/auth/llt"))
    assert llt[3]["Authorization"] == "Bearer acc"


def test_kitchenowl_login_fallback_when_already_onboarded(monkeypatch):
    monkeypatch.setattr(prov, "http", _fake_http({
        "/api/auth/signup": (403, {"msg": "already onboarded"}),
        "/api/onboarding": (403, None),
        "/api/auth": (200, {"access_token": "acc2"}),
        "/api/auth/llt": (200, {"longlived_token": "llt2"}),
    }))
    tok, _ = prov.prov_kitchenowl("http://h:8082", "u", "Name", "pw")
    assert tok == "llt2"


def test_paperless_exchanges_admin_creds_for_token(monkeypatch):
    monkeypatch.setattr(prov, "http", _fake_http({"/api/token/": (200, {"token": "drf_TOKEN"})}))
    tok, _ = prov.prov_paperless("http://h:8081", "admin", "pw")
    assert tok == "drf_TOKEN"


def test_paperless_needs_admin_creds(monkeypatch):
    tok, note = prov.prov_paperless("http://h:8081", None, None)
    assert tok is None and "PAPERLESS_ADMIN" in note


# --------------------------------------------------------------------------- #
# main(): Profil-Filter, Idempotenz, --force, .env-Ausgabe
# --------------------------------------------------------------------------- #
def _setup_main(monkeypatch, tmp_path, env_text):
    env = tmp_path / ".env"
    env.write_text(env_text)
    monkeypatch.setattr(prov, "ENV_PATH", env)
    monkeypatch.setattr(prov, "wait_up", lambda *a, **k: True)  # kein echtes Warten/Netzwerk
    return env


def test_main_noop_without_bundled_services(monkeypatch, tmp_path, capsys):
    _setup_main(monkeypatch, tmp_path, "COMPOSE_PROFILES=agent\n")
    assert prov.main([]) == 0
    assert "nichts zu provisionieren" in capsys.readouterr().out


def test_main_provisions_and_writes_env(monkeypatch, tmp_path):
    env = _setup_main(monkeypatch, tmp_path, "COMPOSE_PROFILES=vikunja,paperless\nPAPERLESS_ADMIN_USER=admin\nPAPERLESS_ADMIN_PASSWORD=pw\n")
    monkeypatch.setattr(prov, "http", _fake_http({
        "/api/v1/register": (201, None),
        "/api/v1/login": (200, {"token": "jwt"}),
        "/api/v1/routes": (200, {"tasks": {"read_all": {}}}),
        "/api/v1/tokens": (200, {"token": "tk_V"}),
        "/api/token/": (200, {"token": "tk_P"}),
    }))
    assert prov.main([]) == 0
    data = prov.read_env(env)
    assert data["VIKUNJA_TOKEN"] == "tk_V"
    assert data["PAPERLESS_TOKEN"] == "tk_P"
    # einheitliche Admin-Zugangsdaten wurden einmalig erzeugt und persistiert
    assert data["BUNDLE_ADMIN_USER"] and data["BUNDLE_ADMIN_PASSWORD"]


def test_main_is_idempotent_and_force_reprovisions(monkeypatch, tmp_path):
    env = _setup_main(monkeypatch, tmp_path, "COMPOSE_PROFILES=vikunja\nVIKUNJA_TOKEN=alt\n")
    fake = _fake_http({
        "/api/v1/register": (201, None),
        "/api/v1/login": (200, {"token": "jwt"}),
        "/api/v1/routes": (200, {"tasks": {"read_all": {}}}),
        "/api/v1/tokens": (200, {"token": "tk_NEU"}),
    })
    monkeypatch.setattr(prov, "http", fake)

    # Ohne --force: vorhandener Token bleibt, kein HTTP-Aufruf
    assert prov.main([]) == 0
    assert prov.read_env(env)["VIKUNJA_TOKEN"] == "alt"
    assert fake.seen == []

    # Mit --force: neu erzeugt
    assert prov.main(["--force"]) == 0
    assert prov.read_env(env)["VIKUNJA_TOKEN"] == "tk_NEU"


def test_main_only_flag_limits_service(monkeypatch, tmp_path):
    env = _setup_main(monkeypatch, tmp_path, "COMPOSE_PROFILES=vikunja,homebox\n")
    fake = _fake_http({
        "/api/v1/register": (201, None),
        "/api/v1/login": (200, {"token": "jwt"}),
        "/api/v1/routes": (200, {"tasks": {"read_all": {}}}),
        "/api/v1/tokens": (200, {"token": "tk_V"}),
    })
    monkeypatch.setattr(prov, "http", fake)
    assert prov.main(["--only", "vikunja"]) == 0
    data = prov.read_env(env)
    assert data.get("VIKUNJA_TOKEN") == "tk_V"
    assert "HOMEBOX_TOKEN" not in data          # homebox nicht angefasst
    assert not any("homebox" in c[1] or ":7745" in c[1] for c in fake.seen)
