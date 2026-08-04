"""MCP-Server (``hermes_family_mcp``) – Haushalts-Werkzeuge für hermes-agent.

Exponiert die bestehende Tool-Registry (``app/ai/tools.py``) als MCP-Server, damit
der NousResearch/hermes-agent die Familien-Module direkt steuern kann
(Einkauf, Kalender, Smart Home, Finanzen, Wartung, Essensplan …).

Betrieb (eigener Dienst, im selben Docker-Netz wie hermes-agent):
    python -m app.mcp.server           # Streamable-HTTP auf MCP_HOST:MCP_PORT

hermes-agent-Seite: einen MCP-Server hinzufügen, der auf
``http://hermes-mcp:8765/mcp`` (Streamable HTTP) zeigt.

Jeder Aufruf öffnet eine eigene DB-Session und handelt mit der Rolle
``MCP_ROLE`` (Standard: partner) – dieselbe rollenbasierte Rechteprüfung wie im
Chat gilt also auch hier.
"""

from __future__ import annotations

from typing import Optional

from mcp.server.fastmcp import FastMCP

from app.ai.tools import TOOLS, ToolContext, is_allowed
from app.config import settings
from app.core.database import SessionLocal
from app.core.logging_config import get_logger

logger = get_logger("mcp.server")

mcp = FastMCP("hermes_family_mcp", host=settings.mcp_host, port=settings.mcp_port)

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}


async def _run(tool_name: str, **kwargs) -> str:
    """Führt ein Hermes-Tool mit frischer DB-Session und MCP-Rolle aus."""
    tool = TOOLS.get(tool_name)
    if not tool:
        return f"Unbekanntes Werkzeug: {tool_name}"
    if not is_allowed(tool.min_role, settings.mcp_role):
        return f"Rolle {settings.mcp_role} darf {tool_name} nicht ausführen."
    db = SessionLocal()
    try:
        ctx = ToolContext(db=db, user_id=None, role=settings.mcp_role)
        return await tool.handler(ctx, **kwargs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("mcp tool %s failed: %s", tool_name, exc)
        return f"Fehler bei {tool_name}: {exc}"
    finally:
        db.close()


# === Lese-Werkzeuge ===

@mcp.tool(name="get_daily_overview", annotations={"title": "Tagesübersicht", **READ})
async def get_daily_overview() -> str:
    """Tagesübersicht: Wetter, Termine, offene Aufgaben und proaktive Hinweise."""
    return await _run("get_daily_overview")


@mcp.tool(name="get_weather", annotations={"title": "Wetter", **READ})
async def get_weather() -> str:
    """Aktuelles Wetter und Vorhersage für morgen."""
    return await _run("get_weather")


@mcp.tool(name="get_calendar", annotations={"title": "Termine", **READ})
async def get_calendar() -> str:
    """Termine der nächsten 7 Tage (CalDAV/Nextcloud)."""
    return await _run("get_calendar")


@mcp.tool(name="get_shopping_list", annotations={"title": "Einkaufsliste", **READ})
async def get_shopping_list() -> str:
    """Zeigt die aktuelle Einkaufsliste (KitchenOwl)."""
    return await _run("get_shopping_list")


@mcp.tool(name="list_tasks", annotations={"title": "Aufgaben", **READ})
async def list_tasks() -> str:
    """Listet offene Aufgaben auf (Vikunja)."""
    return await _run("list_tasks")


@mcp.tool(name="get_finance_overview", annotations={"title": "Finanzen", **READ})
async def get_finance_overview() -> str:
    """Monatliche Fixkosten / wiederkehrende Ausgaben."""
    return await _run("get_finance_overview")


@mcp.tool(name="get_meal_plan", annotations={"title": "Essensplan", **READ})
async def get_meal_plan() -> str:
    """Essensplan der Woche."""
    return await _run("get_meal_plan")


@mcp.tool(name="get_maintenance", annotations={"title": "Wartung", **READ})
async def get_maintenance() -> str:
    """Anstehende Wartungen (nächste 30 Tage)."""
    return await _run("get_maintenance")


@mcp.tool(name="get_smart_home", annotations={"title": "Smart-Home-Status", **READ})
async def get_smart_home() -> str:
    """Smart-Home-Status (Lichter an, offene Türen/Fenster)."""
    return await _run("get_smart_home")


@mcp.tool(name="get_now_playing", annotations={"title": "Läuft gerade", **READ})
async def get_now_playing() -> str:
    """Was gerade läuft: Plex-Streams, Hörbücher, Tonies."""
    return await _run("get_now_playing")


@mcp.tool(name="get_requests", annotations={"title": "Media-Anfragen", **READ})
async def get_requests() -> str:
    """Offene Media-Anfragen (Overseerr)."""
    return await _run("get_requests")


@mcp.tool(name="get_upcoming_media", annotations={"title": "Demnächst (Serien/Filme)", **READ})
async def get_upcoming_media() -> str:
    """Anstehende Serien-Folgen (Sonarr) und Film-Releases (Radarr)."""
    return await _run("get_upcoming_media")


@mcp.tool(name="get_download_queue", annotations={"title": "Download-Queue", **READ})
async def get_download_queue() -> str:
    """Laufende Downloads (Sonarr/Radarr) mit Fortschritt."""
    return await _run("get_download_queue")


@mcp.tool(name="list_packages", annotations={"title": "Pakete", **READ})
async def list_packages() -> str:
    """Listet offene Pakete auf."""
    return await _run("list_packages")


@mcp.tool(name="list_family", annotations={"title": "Familie", **READ})
async def list_family() -> str:
    """Listet die Familienmitglieder auf."""
    return await _run("list_family")


@mcp.tool(name="search", annotations={"title": "Globale Suche", **READ})
async def search(query: str) -> str:
    """Globale Suche über Dokumente, Aufgaben, Inventar etc."""
    return await _run("search", query=query)


# === Handelnde Werkzeuge ===

@mcp.tool(name="add_shopping_item", annotations={"title": "Einkauf: hinzufügen", **WRITE})
async def add_shopping_item(name: str) -> str:
    """Fügt einen Artikel zur Einkaufsliste hinzu (z.B. 'Milch')."""
    return await _run("add_shopping_item", name=name)


@mcp.tool(name="create_task", annotations={"title": "Aufgabe anlegen", **WRITE})
async def create_task(title: str, due_date: Optional[str] = None) -> str:
    """Legt eine neue Aufgabe an (optional mit ISO-Fälligkeitsdatum)."""
    return await _run("create_task", title=title, due_date=due_date)


@mcp.tool(name="create_reminder", annotations={"title": "Erinnerung anlegen", **WRITE})
async def create_reminder(title: str, due_at: Optional[str] = None, priority: str = "info", recurrence: str = "none") -> str:
    """Erstellt eine (ggf. wiederkehrende) Erinnerung.

    recurrence: none | daily | weekdays | weekly | monthly.
    """
    return await _run("create_reminder", title=title, due_at=due_at, priority=priority, recurrence=recurrence)


@mcp.tool(name="add_package", annotations={"title": "Paket hinzufügen", **WRITE})
async def add_package(description: str, tracking_number: Optional[str] = None) -> str:
    """Fügt ein zu verfolgendes Paket hinzu (Carrier wird erkannt)."""
    return await _run("add_package", description=description, tracking_number=tracking_number)


@mcp.tool(name="add_expense", annotations={"title": "Ausgabe anlegen", **WRITE})
async def add_expense(name: str, amount: float, interval: str = "monthly", category: str = "other") -> str:
    """Legt eine wiederkehrende Ausgabe an (Versicherung/Abo/Miete …).

    interval: weekly | monthly | quarterly | yearly.
    """
    return await _run("add_expense", name=name, amount=amount, interval=interval, category=category)


@mcp.tool(name="control_light", annotations={"title": "Licht schalten", **WRITE})
async def control_light(name: str, action: str = "on") -> str:
    """Schaltet ein Licht/einen Schalter (nach Gerätename/Raum). action: on|off."""
    return await _run("control_light", name=name, action=action)


@mcp.tool(name="complete_maintenance", annotations={"title": "Wartung erledigt", **WRITE})
async def complete_maintenance(title: str) -> str:
    """Markiert eine Wartung als erledigt und plant die nächste."""
    return await _run("complete_maintenance", title=title)


@mcp.tool(name="add_meal", annotations={"title": "Mahlzeit einplanen", **WRITE})
async def add_meal(title: str, date: Optional[str] = None, meal_type: str = "dinner") -> str:
    """Plant eine Mahlzeit (Rezept oder freier Text) für ein Datum (YYYY-MM-DD)."""
    return await _run("add_meal", title=title, date=date, meal_type=meal_type)


@mcp.tool(name="generate_shopping_list", annotations={"title": "Einkaufsliste erzeugen", **WRITE})
async def generate_shopping_list(days: int = 7) -> str:
    """Sammelt Zutaten aus dem Essensplan und legt sie in KitchenOwl an."""
    return await _run("generate_shopping_list", days=days)


@mcp.tool(name="add_series", annotations={"title": "Serie herunterladen (Sonarr)", **WRITE})
async def add_series(query: str) -> str:
    """Sucht eine Serie und legt sie in Sonarr zum Download an."""
    return await _run("add_series", query=query)


@mcp.tool(name="add_movie", annotations={"title": "Film herunterladen (Radarr)", **WRITE})
async def add_movie(query: str) -> str:
    """Sucht einen Film und legt ihn in Radarr zum Download an."""
    return await _run("add_movie", query=query)


def main() -> None:
    logger.info("Hermes MCP server on %s:%s (role=%s, streamable-http)", settings.mcp_host, settings.mcp_port, settings.mcp_role)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
