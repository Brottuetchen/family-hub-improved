#!/usr/bin/env python3
"""Vollautomatische API-Token-Provisionierung für die gebündelten Fach-Dienste.

Der Installer ruft dieses Skript NACH dem Start der Container auf. Für jeden
aktiven, selbst-installierten Dienst (aus ``COMPOSE_PROFILES``) wird:

  1. gewartet, bis der Dienst per HTTP antwortet,
  2. der erste Nutzer angelegt bzw. eingeloggt,
  3. ein möglichst dauerhafter API-Token erzeugt,
  4. ``<DIENST>_TOKEN`` in die ``.env`` geschrieben (Upsert, ordnungserhaltend).

Damit entfällt der bisher manuelle Schritt „einloggen → Token erstellen → in die
.env eintragen → neustarten". Es ist echte *volle Automatik*.

Eigenschaften:
  * **Idempotent** – bereits gesetzte Tokens werden übersprungen (außer ``--force``).
  * **Robust** – ein einzelner Fehlschlag bricht NICHT ab; am Ende steht eine
    Zusammenfassung, fehlgeschlagene Dienste bekommen den manuellen Hinweis.
  * **Ohne Extra-Pakete** – nur Standardbibliothek (urllib), läuft mit jedem
    Python 3.11+ (Host-Python genügt, kein venv nötig).

Erreicht werden die Dienste immer über ``http://127.0.0.1:<host-port>`` – das gilt
für Docker- (veröffentlichte Ports) UND lokale Installation gleichermaßen. Die
für Hermes hinterlegten ``*_URL`` (Docker: Service-DNS, lokal: localhost) bleiben
unangetastet; hier wird ausschließlich der Token gesetzt.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"

# host-veröffentlichte Standard-Ports je Dienst (überschreibbar via <X>_PORT).
PORTS = {
    "vikunja": ("VIKUNJA_PORT", 3456),
    "kitchenowl": ("KITCHENOWL_PORT", 8082),
    "paperless": ("PAPERLESS_PORT", 8081),
    "homebox": ("HOMEBOX_PORT", 7745),
}
TOKEN_KEY = {
    "vikunja": "VIKUNJA_TOKEN",
    "kitchenowl": "KITCHENOWL_TOKEN",
    "paperless": "PAPERLESS_TOKEN",
    "homebox": "HOMEBOX_TOKEN",
}
# Endpoint, der „Dienst ist oben" signalisiert (irgendein HTTP-Status < 500).
READY_PATH = {
    "vikunja": "/api/v1/info",
    "kitchenowl": "/api/health",
    "paperless": "/api/",
    "homebox": "/api/v1/status",
}
SERVICES = ("vikunja", "kitchenowl", "paperless", "homebox")


# --------------------------------------------------------------------------- #
# Ausgabe
# --------------------------------------------------------------------------- #
def _c(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if sys.stdout.isatty() else text


def info(msg: str) -> None:
    print(f"  {msg}")


def ok(msg: str) -> None:
    print(_c(f"  ✅ {msg}", "32"))


def warn(msg: str) -> None:
    print(_c(f"  ⚠ {msg}", "33"))


# --------------------------------------------------------------------------- #
# .env I/O
# --------------------------------------------------------------------------- #
def read_env(path: Path | None = None) -> dict:
    path = path or ENV_PATH
    data: dict = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s and not s.startswith("#") and "=" in s:
                k, _, v = s.partition("=")
                data[k.strip()] = v.strip()
    return data


def upsert_env(updates: dict, path: Path | None = None) -> None:
    """Aktualisiert vorhandene Schlüssel bzw. hängt neue an.

    Erhält Kommentare und Reihenfolge – anders als ein kompletter Rewrite, der
    andere Werte gefährden könnte (dieses Skript läuft *nach* dem Setup).
    """
    path = path or ENV_PATH
    if not updates:
        return
    remaining = dict(updates)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s:
            key = s.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    if remaining:
        if out and out[-1].strip():
            out.append("")
        out.append("# Auto-provisioniert (backend/scripts/provision_tokens.py)")
        for key, val in remaining.items():
            out.append(f"{key}={val}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# HTTP (nur Standardbibliothek)
# --------------------------------------------------------------------------- #
class Resp:
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body

    def json(self):
        try:
            return json.loads(self.body)
        except Exception:  # noqa: BLE001
            return None


def http(method: str, url: str, *, headers: dict | None = None,
         data: dict | None = None, form: dict | None = None, timeout: int = 20) -> Resp:
    """Ein HTTP-Request. ``data`` → JSON-Body, ``form`` → urlencoded-Body.

    Gibt IMMER ein ``Resp`` zurück (Status 0 = Verbindungs-/Netzwerkfehler),
    wirft also nie – der Aufrufer entscheidet anhand des Status.
    """
    body: bytes | None = None
    hdrs = dict(headers or {})
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    elif form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
    req = urllib.request.Request(url, data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Resp(getattr(r, "status", 200), r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return Resp(e.code, e.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001  (URLError, TimeoutError, OSError …)
        return Resp(0, str(e))


def wait_up(base: str, ready_path: str, timeout: int = 240, interval: int = 3) -> bool:
    """Wartet, bis der Dienst per HTTP antwortet (Status < 500)."""
    url = base.rstrip("/") + ready_path
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = http("GET", url, timeout=8)
        if r.status and r.status < 500:
            return True
        time.sleep(interval)
    return False


# --------------------------------------------------------------------------- #
# Provisionierung je Dienst  →  (token | None, hinweis)
# --------------------------------------------------------------------------- #
def prov_vikunja(base: str, user: str, email: str, pw: str):
    # 1) Erstnutzer anlegen (Registrierung ist auf frischer Instanz aktiv; ein
    #    „existiert bereits" ist unkritisch – dann folgt einfach der Login).
    http("POST", f"{base}/api/v1/register", data={"username": user, "email": email, "password": pw})
    # 2) Login → JWT.
    r = http("POST", f"{base}/api/v1/login", data={"username": user, "password": pw})
    jwt = (r.json() or {}).get("token") if r.status == 200 else None
    if not jwt:
        return None, f"Login fehlgeschlagen (HTTP {r.status})"
    auth = {"Authorization": f"Bearer {jwt}"}
    # 3) Dauerhaften API-Token mit allen verfügbaren Rechten erzeugen. Die
    #    möglichen Permissions liefert /api/v1/routes (Gruppe → Aktionen).
    routes = http("GET", f"{base}/api/v1/routes", headers=auth)
    perms: dict = {}
    rj = routes.json()
    if isinstance(rj, dict):
        for group, val in rj.items():
            if isinstance(val, dict):
                perms[group] = list(val.keys())
            elif isinstance(val, list):
                perms[group] = val
    if perms:
        exp = (datetime.now(timezone.utc) + timedelta(days=3650)).strftime("%Y-%m-%dT%H:%M:%SZ")
        t = http("PUT", f"{base}/api/v1/tokens", headers=auth,
                 data={"title": "Hermes Family OS", "permissions": perms, "expires_at": exp})
        tok = (t.json() or {}).get("token") if t.status in (200, 201) else None
        if tok:
            return tok, "API-Token (dauerhaft)"
    # 4) Fallback: langlebiges JWT (30 Tage) – falls der API-Token-Endpoint fehlt.
    r2 = http("POST", f"{base}/api/v1/login", data={"username": user, "password": pw, "long_token": True})
    if r2.status == 200 and (r2.json() or {}).get("token"):
        return r2.json()["token"], "JWT (langlebig, ~30 Tage)"
    return jwt, "JWT (kurzlebig – API-Token-Endpoint nicht verfügbar)"


def prov_kitchenowl(base: str, user: str, name: str, pw: str):
    device = "Hermes Family OS"
    access = None
    # 1) Ersten Nutzer anlegen – je nach Version /api/auth/signup oder /api/onboarding.
    for url in (f"{base}/api/auth/signup", f"{base}/api/onboarding"):
        r = http("POST", url, data={"username": user, "name": name, "password": pw, "device": device})
        if r.status == 200:
            access = (r.json() or {}).get("access_token")
            if access:
                break
    # 2) Sonst: bereits eingerichtet → einloggen (Login-Route ist der Blueprint-Root).
    if not access:
        r = http("POST", f"{base}/api/auth", data={"username": user, "password": pw, "device": device})
        if r.status in (404, 405):
            r = http("POST", f"{base}/api/auth/", data={"username": user, "password": pw, "device": device})
        access = (r.json() or {}).get("access_token") if r.status == 200 else None
    if not access:
        return None, "Signup/Login fehlgeschlagen"
    # 3) Long-Lived-Token erzeugen (das ist der dauerhafte API-Token).
    llt = http("POST", f"{base}/api/auth/llt", headers={"Authorization": f"Bearer {access}"},
               data={"device": device})
    tok = (llt.json() or {}).get("longlived_token") if llt.status == 200 else None
    return (tok, "Long-Lived-Token") if tok else (None, f"LLT fehlgeschlagen (HTTP {llt.status})")


def prov_paperless(base: str, user: str | None, pw: str | None):
    # Der Admin wird von Paperless beim ersten Start aus PAPERLESS_ADMIN_USER/…_PASSWORD
    # angelegt. Wir tauschen diese Zugangsdaten gegen einen DRF-API-Token.
    if not user or not pw:
        return None, "PAPERLESS_ADMIN_USER/PASSWORD fehlen in .env"
    r = http("POST", f"{base}/api/token/", data={"username": user, "password": pw})
    if r.status != 200:  # manche Deployments akzeptieren nur Form-Encoding
        r = http("POST", f"{base}/api/token/", form={"username": user, "password": pw})
    tok = (r.json() or {}).get("token") if r.status == 200 else None
    return (tok, "API-Token") if tok else (None, f"Token-Endpoint HTTP {r.status}")


def prov_homebox(base: str, email: str, pw: str):
    # 1) Erstnutzer registrieren (Registrierung via HBOX_OPTIONS_ALLOW_REGISTRATION aktiv).
    http("POST", f"{base}/api/v1/users/register", data={"name": "Hermes", "email": email, "password": pw})
    # 2) Login → Bearer-Token. Homebox liefert den Wert bereits inkl. "Bearer "-Prefix,
    #    der Connector setzt selbst "Bearer " davor → Prefix hier strippen.
    r = http("POST", f"{base}/api/v1/users/login",
             data={"username": email, "password": pw, "stayLoggedIn": True})
    if r.status != 200:
        r = http("POST", f"{base}/api/v1/users/login", form={"username": email, "password": pw})
    raw = (r.json() or {}).get("token") if r.status == 200 else None
    if not raw:
        return None, f"Login fehlgeschlagen (HTTP {r.status})"
    tok = raw[7:] if raw.lower().startswith("bearer ") else raw
    return tok, "Login-Token (verlängert sich bei Nutzung)"


# --------------------------------------------------------------------------- #
# Ablauf
# --------------------------------------------------------------------------- #
def provision_one(svc: str, env: dict, admin_user: str, admin_email: str, admin_pw: str,
                  wait: int):
    """Wartet auf den Dienst und provisioniert seinen Token. → (token|None, hinweis)."""
    port_env, default_port = PORTS[svc]
    port = env.get(port_env) or str(default_port)
    base = f"http://127.0.0.1:{port}"
    info(f"{svc}: warte auf {base} …")
    if not wait_up(base, READY_PATH[svc], timeout=wait):
        return None, "nicht erreichbar (Timeout)"
    if svc == "vikunja":
        return prov_vikunja(base, admin_user, admin_email, admin_pw)
    if svc == "kitchenowl":
        return prov_kitchenowl(base, admin_user, "Hermes", admin_pw)
    if svc == "paperless":
        return prov_paperless(base, env.get("PAPERLESS_ADMIN_USER"), env.get("PAPERLESS_ADMIN_PASSWORD"))
    return prov_homebox(base, admin_email, admin_pw)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Auto-Provisionierung der Dienst-API-Tokens.")
    ap.add_argument("--force", action="store_true", help="auch bereits gesetzte Tokens neu erzeugen")
    ap.add_argument("--only", choices=SERVICES, help="nur diesen Dienst provisionieren")
    ap.add_argument("--wait", type=int, default=240, help="max. Sekunden je Dienst auf Erreichbarkeit warten")
    args = ap.parse_args(argv)

    env = read_env()
    profiles = {p.strip() for p in (env.get("COMPOSE_PROFILES") or "").split(",") if p.strip()}
    services = [s for s in SERVICES if s in profiles and (not args.only or args.only == s)]

    print(_c("\n── Token-Provisionierung (vollautomatisch) ", "1;36"))
    if not services:
        info("Keine gebündelten Dienste mit Token aktiv – nichts zu provisionieren.")
        return 0

    # Einheitliche Admin-Zugangsdaten: einmalig erzeugt, in .env persistiert →
    # eine Anmeldung für alle Fach-Dienste, und Re-Runs bleiben idempotent.
    admin_user = env.get("BUNDLE_ADMIN_USER") or "hermes"
    admin_email = env.get("BUNDLE_ADMIN_EMAIL") or "hermes@family.local"
    admin_pw = env.get("BUNDLE_ADMIN_PASSWORD") or secrets.token_urlsafe(16)
    updates: dict = {}
    if not env.get("BUNDLE_ADMIN_USER"):
        updates["BUNDLE_ADMIN_USER"] = admin_user
    if not env.get("BUNDLE_ADMIN_EMAIL"):
        updates["BUNDLE_ADMIN_EMAIL"] = admin_email
    if not env.get("BUNDLE_ADMIN_PASSWORD"):
        updates["BUNDLE_ADMIN_PASSWORD"] = admin_pw

    results: list[tuple[str, bool, str]] = []
    for svc in services:
        key = TOKEN_KEY[svc]
        if env.get(key) and not args.force:
            info(f"{svc}: Token bereits gesetzt – übersprungen (--force zum Neuerzeugen).")
            results.append((svc, True, "vorhanden"))
            continue
        token, note = provision_one(svc, env, admin_user, admin_email, admin_pw, args.wait)
        if token:
            updates[key] = token
            ok(f"{svc}: {note}")
            results.append((svc, True, note))
        else:
            warn(f"{svc}: {note}")
            results.append((svc, False, note))

    upsert_env(updates)

    good = [s for s, o, _ in results if o]
    bad = [s for s, o, _ in results if not o]
    print()
    if good:
        ok(f"bereit: {', '.join(good)}")
    if bad:
        warn(f"manuell nachziehen: {', '.join(bad)}")
        info("  → Web-UI öffnen, API-Token erstellen, in .env als <DIENST>_TOKEN eintragen, Hermes neu starten.")
    if any(k in updates for k in TOKEN_KEY.values()):
        info("Tokens in .env geschrieben – Hermes übernimmt sie beim (Neu-)Start.")
    # Nie hart fehlschlagen: der Installer soll trotz Teil-Fehlern sauber enden.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
