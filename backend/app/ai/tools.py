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
from app.core.security import ROLE_LEVEL
from app.models.family import FamilyMember
from app.models.finance import RecurringExpense
from app.models.maintenance import MaintenanceTask
from app.models.package import Package
from app.models.recipe import MealPlanEntry, Recipe
from app.models.reminder import Reminder


@dataclass
class ToolContext:
    db: Session
    user_id: Optional[int] = None
    # Rolle des aktuellen Nutzers – steuert, welche Werkzeuge erlaubt sind.
    role: str = "partner"


def is_allowed(min_role: str, user_role: str) -> bool:
    return ROLE_LEVEL.get(user_role, 0) >= ROLE_LEVEL.get(min_role, 0)


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Awaitable[str]]
    # Mindest-Rolle, um dieses Werkzeug zu nutzen (guest < child < partner < admin).
    min_role: str = "guest"

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


async def _get_calendar(ctx: ToolContext) -> str:
    cal = registry.get("caldav")
    if not cal or not cal.is_configured:
        return "Kalender (CalDAV) ist nicht konfiguriert."
    events = await cal.get_events(days_ahead=7)  # type: ignore[attr-defined]
    if not events:
        return "Keine Termine in den nächsten 7 Tagen."
    lines = ["📅 Termine:"]
    for e in events[:8]:
        lines.append(f"   • {e.get('title')} ({e.get('start', '')})")
    return "\n".join(lines)


async def _get_smart_home(ctx: ToolContext) -> str:
    ha = registry.get("homeassistant")
    if not ha or not ha.is_configured:
        return "Smart Home (Home Assistant) ist nicht konfiguriert."
    ov = await ha.get_overview()  # type: ignore[attr-defined]
    return f"🏠 {ov.get('lights_on', 0)} Lichter an, {ov.get('doors_windows_open', 0)} Türen/Fenster offen."


async def _control_light(ctx: ToolContext, name: str, action: str = "on") -> str:
    ha = registry.get("homeassistant")
    if not ha or not ha.is_configured:
        return "Smart Home (Home Assistant) ist nicht konfiguriert."
    svc = "turn_on" if str(action).lower() in ("on", "an", "ein", "einschalten", "anmachen", "turn_on", "true") else "turn_off"
    states = await ha.get_states()  # type: ignore[attr-defined]
    cand = [
        s for s in states
        if s["entity_id"].split(".")[0] in ("light", "switch") and name.lower() in (s.get("name") or "").lower()
    ]
    if not cand:
        return f"Kein schaltbares Gerät '{name}' gefunden."
    ent = cand[0]["entity_id"]
    ok = await ha.call_service(ent.split(".")[0], svc, ent)  # type: ignore[attr-defined]
    verb = "eingeschaltet" if svc == "turn_on" else "ausgeschaltet"
    return f"{cand[0]['name']} {verb}. 💡" if ok else "Konnte das Gerät nicht schalten."


async def _add_package(ctx: ToolContext, description: str, tracking_number: Optional[str] = None, carrier: str = "auto") -> str:
    from app.services.tracking import detect_carrier

    c = detect_carrier(tracking_number) if (not carrier or carrier == "auto") else carrier
    ctx.db.add(Package(carrier=c, tracking_number=tracking_number, description=description, status="in_transit"))
    ctx.db.commit()
    return f"Paket '{description}' ({c.upper()}) wird jetzt verfolgt. 📦"


async def _list_packages(ctx: ToolContext) -> str:
    pkgs = ctx.db.query(Package).filter(Package.status != "delivered").all()
    if not pkgs:
        return "Keine offenen Pakete."
    return "📦 Pakete:\n" + "\n".join(
        f"   • {p.carrier.upper()}: {p.description or p.tracking_number or 'Paket'} ({p.status})" for p in pkgs
    )


async def _add_expense(ctx: ToolContext, name: str, amount: float, interval: str = "monthly", category: str = "other") -> str:
    try:
        amt = float(amount)
    except (TypeError, ValueError):
        amt = 0.0
    interval = interval if interval in {"weekly", "monthly", "quarterly", "yearly"} else "monthly"
    ctx.db.add(RecurringExpense(name=name, amount=amt, interval=interval, category=category))
    ctx.db.commit()
    return f"Kostenposten '{name}' ({amt:.2f} €, {interval}) gespeichert. 💶"


async def _get_maintenance(ctx: ToolContext) -> str:
    from datetime import date, timedelta

    tasks = (
        ctx.db.query(MaintenanceTask)
        .filter(MaintenanceTask.next_due != None)  # noqa: E711
        .filter(MaintenanceTask.next_due <= date.today() + timedelta(days=30))
        .all()
    )
    if not tasks:
        return "Keine anstehenden Wartungen."
    return "🔧 Wartung:\n" + "\n".join(f"   • {t.title} (fällig {t.next_due.strftime('%d.%m.')})" for t in tasks)


async def _complete_maintenance(ctx: ToolContext, title: str) -> str:
    from datetime import date, timedelta

    t = ctx.db.query(MaintenanceTask).filter(MaintenanceTask.title.ilike(f"%{title}%")).first()
    if not t:
        return f"Keine Wartung '{title}' gefunden."
    t.last_done = date.today()
    if t.interval_days:
        t.next_due = date.today() + timedelta(days=t.interval_days)
    ctx.db.commit()
    return f"'{t.title}' als erledigt markiert. ✅"


async def _add_meal(ctx: ToolContext, title: str, date: Optional[str] = None, meal_type: str = "dinner") -> str:
    from datetime import date as date_cls

    day = date or date_cls.today().isoformat()
    recipe = ctx.db.query(Recipe).filter(Recipe.title.ilike(f"%{title}%")).first()
    ctx.db.add(MealPlanEntry(date=day, meal_type=meal_type, recipe_id=recipe.id if recipe else None, custom_title=None if recipe else title))
    ctx.db.commit()
    return f"'{title}' für {day} eingeplant. 🍽️"


async def _generate_shopping_list(ctx: ToolContext, days: int = 7) -> str:
    from app.routers.meals import _collect_ingredients

    ingredients = _collect_ingredients(ctx.db, days)
    if not ingredients:
        return "Keine Rezepte im Zeitraum geplant."
    shopping = registry.get("kitchenowl")
    added = 0
    if shopping and shopping.is_configured:
        for ing in ingredients:
            if await shopping.add_item(ing):  # type: ignore[attr-defined]
                added += 1
    return f"{len(ingredients)} Zutaten gesammelt" + (f", {added} zu KitchenOwl hinzugefügt." if added else ".")


async def _list_family(ctx: ToolContext) -> str:
    members = ctx.db.query(FamilyMember).all()
    if not members:
        return "Keine Familienmitglieder angelegt."
    return "👪 Familie:\n" + "\n".join(f"   • {m.name} ({m.role})" for m in members)


async def _get_requests(ctx: ToolContext) -> str:
    ov = registry.get("overseerr")
    if not ov or not ov.is_configured:
        return "Overseerr ist nicht konfiguriert."
    reqs = await ov.get_pending_requests()  # type: ignore[attr-defined]
    if not reqs:
        return "Keine offenen Media-Anfragen."
    return "🎞️ Offene Anfragen:\n" + "\n".join(f"   • {r['title']} (von {r['requested_by']})" for r in reqs)


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
    "get_calendar": Tool(
        name="get_calendar",
        description="Zeigt die Termine der nächsten 7 Tage.",
        parameters={"type": "object", "properties": {}},
        handler=_get_calendar,
    ),
    "get_smart_home": Tool(
        name="get_smart_home",
        description="Zeigt den Smart-Home-Status (Lichter an, offene Türen/Fenster).",
        parameters={"type": "object", "properties": {}},
        handler=_get_smart_home,
        min_role="child",
    ),
    "control_light": Tool(
        name="control_light",
        description="Schaltet ein Licht/einen Schalter an oder aus (nach Gerätename).",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name/Raum des Geräts, z.B. 'Wohnzimmer'"},
                "action": {"type": "string", "enum": ["on", "off"]},
            },
            "required": ["name", "action"],
        },
        handler=_control_light,
        min_role="partner",
    ),
    "add_package": Tool(
        name="add_package",
        description="Fügt ein zu verfolgendes Paket hinzu (Carrier wird ggf. erkannt).",
        parameters={
            "type": "object",
            "properties": {
                "description": {"type": "string"},
                "tracking_number": {"type": "string"},
            },
            "required": ["description"],
        },
        handler=_add_package,
    ),
    "list_packages": Tool(
        name="list_packages",
        description="Listet offene Pakete auf.",
        parameters={"type": "object", "properties": {}},
        handler=_list_packages,
    ),
    "add_expense": Tool(
        name="add_expense",
        description="Legt eine wiederkehrende Ausgabe an (Versicherung/Abo/Miete …).",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "amount": {"type": "number"},
                "interval": {"type": "string", "enum": ["weekly", "monthly", "quarterly", "yearly"]},
                "category": {"type": "string"},
            },
            "required": ["name", "amount"],
        },
        handler=_add_expense,
        min_role="partner",
    ),
    "get_maintenance": Tool(
        name="get_maintenance",
        description="Zeigt anstehende Wartungen (nächste 30 Tage).",
        parameters={"type": "object", "properties": {}},
        handler=_get_maintenance,
        min_role="child",
    ),
    "complete_maintenance": Tool(
        name="complete_maintenance",
        description="Markiert eine Wartung als erledigt und plant die nächste.",
        parameters={"type": "object", "properties": {"title": {"type": "string"}}, "required": ["title"]},
        handler=_complete_maintenance,
        min_role="partner",
    ),
    "add_meal": Tool(
        name="add_meal",
        description="Plant eine Mahlzeit (Rezept oder freier Text) für ein Datum ein.",
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "date": {"type": "string", "description": "YYYY-MM-DD (optional, Standard heute)"},
                "meal_type": {"type": "string", "enum": ["breakfast", "lunch", "dinner"]},
            },
            "required": ["title"],
        },
        handler=_add_meal,
    ),
    "generate_shopping_list": Tool(
        name="generate_shopping_list",
        description="Erzeugt aus dem Essensplan eine Einkaufsliste (fügt sie KitchenOwl hinzu).",
        parameters={"type": "object", "properties": {"days": {"type": "integer"}}},
        handler=_generate_shopping_list,
    ),
    "list_family": Tool(
        name="list_family",
        description="Listet die Familienmitglieder auf.",
        parameters={"type": "object", "properties": {}},
        handler=_list_family,
    ),
    "get_requests": Tool(
        name="get_requests",
        description="Zeigt offene Media-Anfragen (Overseerr).",
        parameters={"type": "object", "properties": {}},
        handler=_get_requests,
    ),
}


def openai_tools(role: str = "admin") -> List[Dict[str, Any]]:
    """Tool-Schemas – gefiltert nach der Rolle des Nutzers."""
    return [t.openai_schema() for t in TOOLS.values() if is_allowed(t.min_role, role)]
