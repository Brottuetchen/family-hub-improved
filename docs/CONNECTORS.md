# Connectors entwickeln

Ein **Connector** verbindet Hermes mit einem Fachsystem. Er kapselt Authentifizierung,
HTTP-Aufrufe und die Übersetzung in einheitliche Datenformen.

## BaseConnector

Alle Connectors erben von `app.connectors.base.BaseConnector` und setzen:

| Attribut/Methode      | Zweck |
|-----------------------|-------|
| `name`                | technischer, eindeutiger Name (z.B. `"vikunja"`) |
| `display_name`        | Anzeigename für die UI |
| `category`            | `calendar`/`tasks`/`shopping`/… |
| `icon`                | Emoji für die UI |
| `is_configured`       | `bool` – liegt genügend Konfiguration vor? |
| `base_url`            | Basis-URL des Fachsystems |
| `_auth_headers()`     | Auth-Header (Token o.ä.) |
| `_probe()`            | leichte Erreichbarkeitsprüfung für Health-Checks |
| `search(query,limit)` | optional: Beitrag zur globalen Suche |

Hilfsmethoden der Basis: `_client()` (vorkonfigurierter `httpx.AsyncClient` mit
Timeout & TLS-Einstellung) und `_get_json(path, **kw)`.

## Beispiel (minimal)

```python
from typing import Any, Dict, List, Optional
from app.config import settings
from app.connectors.base import BaseConnector

class MyServiceConnector(BaseConnector):
    name = "myservice"
    display_name = "Mein Dienst"
    category = "tasks"
    icon = "🧩"

    @property
    def is_configured(self) -> bool:
        return bool(settings.myservice_url and settings.myservice_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.myservice_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.myservice_token}"}

    async def _probe(self) -> bool:
        await self._get_json("/api/ping")
        return True

    async def get_items(self) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []                       # Graceful Degradation!
        try:
            data = await self._get_json("/api/items")
            return data.get("items", [])
        except Exception as exc:            # niemals das Dashboard crashen
            self.logger.warning("myservice failed: %s", exc)
            return []
```

## Schritte

1. **Settings ergänzen** in `app/config.py`
   (`myservice_url`, `myservice_token`) und in `.env.example` dokumentieren.
2. **Connector-Datei** unter `app/connectors/myservice_connector.py` anlegen.
3. **Registrieren** in `app/connectors/registry.py` (Import + in die Klassen-Tuple).
4. **Router** (optional) unter `app/routers/` für modul-spezifische Endpunkte;
   in `app/main.py` einhängen.
5. **KI-Werkzeug** (optional) in `app/ai/tools.py` hinzufügen.

## Regeln

- **Nie werfen, wenn nicht konfiguriert** – `is_configured` prüfen und `[]`/`{}` liefern.
- **Fehler fangen & loggen** – API-Ausfälle dürfen das Dashboard nicht blockieren.
- **Einheitliche Suchform** für `search()`:
  ```python
  {"title": str, "subtitle": str, "url": str, "source": str, "category": str, "icon": str}
  ```
- **Kurze Timeouts** – die Basis nutzt `settings.connector_timeout` (Default 6s).

## Vorhandene Connectors

`weather` (Open-Meteo), `caldav` (Nextcloud/CalDAV), `vikunja`, `kitchenowl`,
`paperless`, `homebox`, `homeassistant`, `plex`, `audiobookshelf`,
`teddycloud` (Tonies), `overseerr` (Media-Requests).

Die Medien-Connectoren speisen den vereinten `/api/media/now-playing`-Endpunkt
(„Läuft gerade": Plex-Streams + Hörbücher + Tonies) und das Dashboard-Widget.
