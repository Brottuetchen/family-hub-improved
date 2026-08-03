"""Werkzeuge (Tools) für Hermes AI.

Jedes Tool ist eine konkrete Fähigkeit, die der Assistent ausführen kann –
angebunden an die Connectors und die Datenbank. Die Tools werden sowohl vom
LLM (Function Calling) als auch vom regelbasierten Fallback genutzt.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.connectors.registry import registry
from app.models.finance import RecurringExpense
from app.models.recipe import MealPlanEntry, Recipe
from app.models.reminder import Reminder


@dataclass
class ToolContext:
    db: Session
    user_id: Optional[int] = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Awaitable[str]]

    def openai_schema(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# === Tool-Implementierungen ===

async def _get_daily_overview(ctx: ToolContext) -> str:
    from app.services.insights import generate_insights

    lines: List[str] = ["📋 Tagesübersicht:"]

    weather = registry.get("weather")
    if weather and weather.is_configured:
        cur = await weather.get_current()  # type: ignore[attr-defined]
        if cur:
            lines.append(
                f"{cur.get('icon', '')} {cur.get('temperature')}°C, {cur.get('description')} in {cur.get('location')}"
            )

    calendar = registry.get("caldav")
    if calendar and calendar.is_configured:
        events = await calendar.get_today()  # type: ignore[attr-defined]
        if events:
            lines.append(f"📅 {len(events)} Termine heute:")
            for e in events[:5]:
                lines.append(f"   • {e.get('title')}")
        else:
            lines.append("📅 Keine Termine heute.")

    tasks = registry.get("vikunja")
    if tasks and tasks.is_configured:
        open_tasks = await tasks.get_tasks()  # type: ignore[attr-defined]
        lines.append(f"✅ {len(open_tasks)} offene Aufgaben.")

    insights = await generate_insights(ctx.db)
    if insights:
        lines.append("💡 Hinweise:")
        for i in insights[:5]:
            lines.append(f"   {i.get('icon', '•')} {i.get('title')}: {i.get('message')}")

    return "\n".join(lines)


async def _get_weather(ctx: ToolContext) -> str:
    weather = registry.get("weather")
    if not weather or not weather.is_configured:
        return "Wetter ist nicht konfiguriert."
    cur = await weather.get_current()  # type: ignore[attr-defined]
    forecast = await weather.get_forecast(days=2)  # type: ignore[attr-defined]
    out = [f"{cur.get('icon', '')} Aktuell: {cur.get('temperature')}°C, {cur.get('description')}"]
    if len(forecast) > 1:
        t = forecast[1]
        out.append(
            f"Morgen: {t.get('icon', '')} {t.get('temp_min')}–{t.get('temp_max')}°C, "
            f"Regenwahrscheinlichkeit {t.get('precip_probability')}%"
        )
    return "\n".join(out)


async def _add_shopping_item(ctx: ToolContext, name: str) -> str:
    shopping = registry.get("kitchenowl")
    if not shopping or not shopping.is_configured:
        return "Einkaufsliste (KitchenOwl) ist nicht konfiguriert."
    result = await shopping.add_item(name)  # type: ignore[attr-defined]
    if result:
        return f"'{name}' wurde zur Einkaufsliste hinzugefügt. 🛒"
    return f"Konnte '{name}' nicht hinzufügen."


async def _get_shopping_list(ctx: ToolContext) -> str:
    shopping = registry.get("kitchenowl")
    if not shopping or not shopping.is_configured:
        return "Einkaufsliste (KitchenOwl) ist nicht konfiguriert."
    items = await shopping.get_items()  # type: ignore[attr-defined]
    if not items:
        return "Die Einkaufsliste ist leer."
    names = ", ".join(i.get("name", "?") for i in items)
    return f"Auf der Einkaufsliste ({len(items)}): {names}"


async def _create_task(ctx: ToolContext, title: str, due_date: Optional[str] = None) -> str:
    tasks = registry.get("vikunja")
    if not tasks or not tasks.is_configured:
        return "Aufgaben (Vikunja) sind nicht konfiguriert."
    result = await tasks.create_task(title=title, due_date=due_date)  # type: ignore[attr-defined]
    if result:
        return f"Aufgabe '{title}' wurde angelegt. ✅"
    return f"Konnte Aufgabe '{title}' nicht anlegen."


async def _list_tasks(ctx: ToolContext) -> str:
    tasks = registry.get("vikunja")
    if not tasks or not tasks.is_configured:
        return "Aufgaben (Vikunja) sind nicht konfiguriert."
    open_tasks = await tasks.get_tasks()  # type: ignore[attr-defined]
    if not open_tasks:
        return "Keine offenen Aufgaben. 🎉"
    lines = [f"{len(open_tasks)} offene Aufgaben:"]
    for t in open_tasks[:10]:
        lines.append(f"   • {t.get('title')}")
    return "\n".join(lines)


async def _create_reminder(
    ctx: ToolContext,
    title: str,
    due_at: Optional[str] = None,
    priority: str = "info",
    recurrence: str = "none",
) -> str:
    from app.services.recurrence import VALID_RECURRENCE, label

    parsed_due = None
    if due_at:
        try:
            parsed_due = datetime.fromisoformat(due_at.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            parsed_due = None
    if recurrence not in VALID_RECURRENCE:
        recurrence = "none"
    reminder = Reminder(
        title=title,
        due_at=parsed_due,
        priority=priority if priority in {"critical", "important", "info"} else "info",
        recurrence=recurrence,
        source="ai",
        created_by=ctx.user_id,
    )
    ctx.db.add(reminder)
    ctx.db.commit()
    when = f" (fällig {parsed_due.strftime('%d.%m. %H:%M')})" if parsed_due else ""
    rec = f", {label(recurrence)}" if recurrence != "none" else ""
    return f"Erinnerung '{title}'{when}{rec} wurde gespeichert. ⏰"


async def _get_finance_overview(ctx: ToolContext) -> str:
    factor = {"weekly": 52 / 12, "monthly": 1.0, "quarterly": 1 / 3, "yearly": 1 / 12}
    expenses = ctx.db.query(RecurringExpense).filter(RecurringExpense.active == True).all()  # noqa: E712
    if not expenses:
        return "Keine wiederkehrenden Kosten hinterlegt."
    monthly = sum((e.amount or 0.0) * factor.get(e.interval, 1.0) for e in expenses)
    return f"Monatliche Fixkosten: {monthly:.2f} € ({len(expenses)} Posten, {monthly * 12:.2f} €/Jahr)."


async def _get_now_playing(ctx: ToolContext) -> str:
    parts: List[str] = []
    plex = registry.get("plex")
    if plex and plex.is_configured:
        for s in await plex.get_active_streams():  # type: ignore[attr-defined]
            parts.append(f"🎬 {s.get('title')} ({s.get('user')})")
    absc = registry.get("audiobookshelf")
    if absc and absc.is_configured:
        for s in await absc.get_active_sessions():  # type: ignore[attr-defined]
            parts.append(f"📚 {s.get('title')} ({s.get('user')})")
    teddy = registry.get("teddycloud")
    if teddy and teddy.is_configured:
        for s in await teddy.get_active_tonies():  # type: ignore[attr-defined]
            parts.append(f"🧸 {s.get('title')} ({s.get('user')})")
    if not parts:
        return "Gerade läuft nichts (oder Medien-Connectoren sind nicht konfiguriert)."
    return "▶️ Läuft gerade:\n" + "\n".join(f"   {p}" for p in parts)


async def _get_meal_plan(ctx: ToolContext) -> str:
    from datetime import date, timedelta

    today = date.today()
    end = today + timedelta(days=7)
    entries = (
        ctx.db.query(MealPlanEntry)
        .filter(MealPlanEntry.date >= today.isoformat(), MealPlanEntry.date <= end.isoformat())
        .order_by(MealPlanEntry.date.asc())
        .all()
    )
    if not entries:
        return "Für diese Woche ist noch nichts geplant."
    recipes = {r.id: r.title for r in ctx.db.query(Recipe).all()}
    lines = ["🍽️ Essensplan:"]
    for e in entries:
        title = e.custom_title or recipes.get(e.recipe_id, "Mahlzeit")
        lines.append(f"   • {e.date}: {title}")
    return "\n".join(lines)


async def _search(ctx: ToolContext, query: str) -> str:
    results = await registry.search_all(query)
    if not results:
        return f"Keine Treffer für '{query}'."
    lines = [f"{len(results)} Treffer für '{query}':"]
    for r in results[:10]:
        lines.append(f"   {r.get('icon', '•')} [{r.get('source')}] {r.get('title')}")
    return "\n".join(lines)


# === Registry ===

TOOLS: Dict[str, Tool] = {
    "get_daily_overview": Tool(
        name="get_daily_overview",
        description="Liefert die Tagesübersicht: Wetter, Termine, offene Aufgaben und Hinweise. Für 'Was steht heute an?'.",
        parameters={"type": "object", "properties": {}},
        handler=_get_daily_overview,
    ),
    "get_weather": Tool(
        name="get_weather",
        description="Aktuelles Wetter und Vorhersage für morgen.",
        parameters={"type": "object", "properties": {}},
        handler=_get_weather,
    ),
    "add_shopping_item": Tool(
        name="add_shopping_item",
        description="Fügt einen Artikel zur Einkaufsliste hinzu. z.B. 'Milch', 'Brot'.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Name des Artikels"}},
            "required": ["name"],
        },
        handler=_add_shopping_item,
    ),
    "get_shopping_list": Tool(
        name="get_shopping_list",
        description="Zeigt die aktuelle Einkaufsliste.",
        parameters={"type": "object", "properties": {}},
        handler=_get_shopping_list,
    ),
    "create_task": Tool(
        name="create_task",
        description="Legt eine neue Aufgabe an.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Titel der Aufgabe"},
                "due_date": {"type": "string", "description": "Fälligkeitsdatum ISO 8601 (optional)"},
            },
            "required": ["title"],
        },
        handler=_create_task,
    ),
    "list_tasks": Tool(
        name="list_tasks",
        description="Listet offene Aufgaben auf.",
        parameters={"type": "object", "properties": {}},
        handler=_list_tasks,
    ),
    "create_reminder": Tool(
        name="create_reminder",
        description="Erstellt eine Erinnerung, z.B. 'Heute Abend an den Müll denken' oder wiederkehrend 'jeden Dienstag 19 Uhr Müll'.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "due_at": {"type": "string", "description": "Zeitpunkt ISO 8601 (optional)"},
                "priority": {"type": "string", "enum": ["critical", "important", "info"]},
                "recurrence": {
                    "type": "string",
                    "enum": ["none", "daily", "weekdays", "weekly", "monthly"],
                    "description": "Wiederholung (optional)",
                },
            },
            "required": ["title"],
        },
        handler=_create_reminder,
    ),
    "search": Tool(
        name="search",
        description="Globale Suche über Dokumente, Aufgaben, Inventar etc.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        handler=_search,
    ),
    "get_finance_overview": Tool(
        name="get_finance_overview",
        description="Zeigt die monatlichen Fixkosten / wiederkehrenden Ausgaben.",
        parameters={"type": "object", "properties": {}},
        handler=_get_finance_overview,
    ),
    "get_meal_plan": Tool(
        name="get_meal_plan",
        description="Zeigt den Essensplan der Woche.",
        parameters={"type": "object", "properties": {}},
        handler=_get_meal_plan,
    ),
    "get_now_playing": Tool(
        name="get_now_playing",
        description="Zeigt, was gerade in der Familie läuft: Plex-Streams, Hörbücher, Tonies.",
        parameters={"type": "object", "properties": {}},
        handler=_get_now_playing,
    ),
}


def openai_tools() -> List[Dict[str, Any]]:
    return [t.openai_schema() for t in TOOLS.values()]
