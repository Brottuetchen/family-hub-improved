"""Hermes-Agent.

Orchestriert die Werkzeuge. Zwei Betriebsmodi:
  * **LLM-Modus** (wenn konfiguriert): echtes Function-Calling mit Tool-Loop.
  * **Fallback-Modus** (ohne LLM): regelbasierte Intent-Erkennung für die
    wichtigsten deutschen Kommandos ("Bestell Milch", "Was steht heute an?",
    "Erinnere mich heute Abend an den Müll", ...).
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.llm import llm_client
from app.ai.tools import TOOLS, ToolContext, is_allowed, openai_tools
from app.core.logging_config import get_logger
from app.models.user import User
from app.services.recurrence import WEEKDAYS_DE, next_at, next_weekday

logger = get_logger("ai.agent")

SYSTEM_PROMPT = (
    "Du bist Hermes, der Assistent eines Familien-Betriebssystems. "
    "Du hilfst bei Terminen, Aufgaben, Einkäufen, Erinnerungen und dem Smart Home. "
    "Nutze die verfügbaren Werkzeuge, um Aktionen wirklich auszuführen, statt sie nur zu beschreiben. "
    "Antworte kurz, freundlich und auf Deutsch."
)

MAX_ITERATIONS = 5


async def run_agent(
    message: str,
    db: Session,
    user_id: Optional[int] = None,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    role = (user.role if user else None) or "partner"
    name = (user.full_name or user.username) if user else "jemand"
    ctx = ToolContext(db=db, user_id=user_id, role=role)

    if llm_client.is_configured:
        try:
            return await _run_llm(message, ctx, history or [], name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM agent failed, falling back to rules: %s", exc)
    return await _run_rules(message, ctx)


async def _execute_tool(name: str, ctx: ToolContext, args: Dict[str, Any]) -> str:
    tool = TOOLS.get(name)
    if not tool:
        return f"Unbekanntes Werkzeug: {name}"
    if not is_allowed(tool.min_role, ctx.role):
        return f"Das darf deine Rolle ({ctx.role}) nicht. Frag ein Elternteil/Admin."
    try:
        return await tool.handler(ctx, **args)
    except TypeError as exc:
        return f"Ungültige Parameter für {name}: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool %s failed: %s", name, exc)
        return f"Fehler bei {name}: {exc}"


async def _run_llm(message: str, ctx: ToolContext, history: List[Dict[str, str]], user_name: str) -> Dict[str, Any]:
    system = (
        f"{SYSTEM_PROMPT}\n\nDu sprichst gerade mit {user_name} (Rolle: {ctx.role}). "
        "Neu erstellte Einträge gehören dieser Person. "
        "Führe nur Aktionen aus, die dieser Rolle erlaubt sind."
    )
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    executed: List[str] = []
    for _ in range(MAX_ITERATIONS):
        msg = await llm_client.chat(messages, tools=openai_tools(ctx.role))
        tool_calls = msg.get("tool_calls")
        if not tool_calls:
            return {"reply": msg.get("content", ""), "actions": executed, "used_llm": True}

        messages.append(msg)
        for tc in tool_calls:
            fn = tc.get("function", {})
            name = fn.get("name")
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = await _execute_tool(name, ctx, args)
            executed.append(name)
            messages.append(
                {"role": "tool", "tool_call_id": tc.get("id"), "content": result}
            )

    return {"reply": "Ich konnte die Anfrage nicht abschließen.", "actions": executed, "used_llm": True}


# === Regelbasierter Fallback ===

async def _run_rules(message: str, ctx: ToolContext) -> Dict[str, Any]:
    text = message.strip()
    low = text.lower()

    # Tagesübersicht / Morgenübersicht
    if re.search(r"\b(was steht (heute )?an|tages(übersicht|plan)|morgen(übersicht|routine)|überblick)\b", low):
        reply = await _execute_tool("get_daily_overview", ctx, {})
        return _reply(reply, "get_daily_overview")

    # Wetter
    if re.search(r"\bwetter\b|regnet|regen|sonne", low):
        reply = await _execute_tool("get_weather", ctx, {})
        return _reply(reply, "get_weather")

    # Einkaufsliste anzeigen
    if re.search(r"(zeig|was ist auf|inhalt).*(einkaufs?liste)|einkaufsliste\??$", low):
        reply = await _execute_tool("get_shopping_list", ctx, {})
        return _reply(reply, "get_shopping_list")

    # Zur Einkaufsliste hinzufügen
    item = _extract_shopping_item(text)
    if item:
        reply = await _execute_tool("add_shopping_item", ctx, {"name": item})
        return _reply(reply, "add_shopping_item")

    # Erinnerung
    reminder = _extract_reminder(text)
    if reminder:
        reply = await _execute_tool("create_reminder", ctx, reminder)
        return _reply(reply, "create_reminder")

    # Aufgabe / Planung
    task_title = _extract_task(text)
    if task_title:
        reply = await _execute_tool("create_task", ctx, {"title": task_title})
        return _reply(reply, "create_task")

    # Aufgabenliste
    if re.search(r"(offene )?aufgaben|to-?dos?\b", low):
        reply = await _execute_tool("list_tasks", ctx, {})
        return _reply(reply, "list_tasks")

    # Finanzen
    if re.search(r"fixkosten|finanzen|ausgaben|was\s+kostet|monatliche?\s+kosten", low):
        reply = await _execute_tool("get_finance_overview", ctx, {})
        return _reply(reply, "get_finance_overview")

    # Essensplan
    if re.search(r"essensplan|men[üu]plan|koch|essen.*woche|woche.*essen|gibt.?s?.*essen|was.*zu\s+essen", low):
        reply = await _execute_tool("get_meal_plan", ctx, {})
        return _reply(reply, "get_meal_plan")

    # Medien: was läuft gerade
    if re.search(r"was läuft|läuft gerade|was hören|was schau|was guck|tonie|hörbuch|plex", low):
        reply = await _execute_tool("get_now_playing", ctx, {})
        return _reply(reply, "get_now_playing")

    # Smart Home: Licht schalten
    if re.search(r"\b(licht|lampe|lampen|beleuchtung)\b", low) and re.search(
        r"\b(an|aus|ein|anmachen|ausmachen|einschalten|ausschalten)\b", low
    ):
        action = "on" if re.search(r"\b(an|ein|anmachen|einschalten)\b", low) else "off"
        reply = await _execute_tool("control_light", ctx, {"name": _extract_light_name(text), "action": action})
        return _reply(reply, "control_light")

    # Kalender / Termine
    if re.search(r"\btermin(e)?\b|\bkalender\b", low):
        reply = await _execute_tool("get_calendar", ctx, {})
        return _reply(reply, "get_calendar")

    # Pakete
    if re.search(r"\bpaket|lieferung|sendung", low):
        reply = await _execute_tool("list_packages", ctx, {})
        return _reply(reply, "list_packages")

    # Familie
    if re.search(r"\bfamilie\b|mitglieder|wer gehört", low):
        reply = await _execute_tool("list_family", ctx, {})
        return _reply(reply, "list_family")

    # Suche
    q = _extract_search(text)
    if q:
        reply = await _execute_tool("search", ctx, {"query": q})
        return _reply(reply, "search")

    # Hilfe / Default
    return _reply(
        "Ich bin Hermes 👋 Ich kann z.B.:\n"
        "• 'Was steht heute an?'\n"
        "• 'Bestell Milch' / 'Milch ist leer'\n"
        "• 'Erinnere mich heute Abend an den Müll'\n"
        "• 'Neue Aufgabe: Fahrrad reparieren'\n"
        "• 'Wie ist das Wetter?'\n"
        "• 'Suche nach Versicherung'",
        None,
    )


def _reply(text: str, action: Optional[str]) -> Dict[str, Any]:
    return {"reply": text, "actions": [action] if action else [], "used_llm": False}


def _extract_shopping_item(text: str) -> Optional[str]:
    low = text.lower()
    # "Milch ist leer" -> Milch
    m = re.search(r"^(.*?)\s+ist\s+(leer|alle|aus)\b", low)
    if m and m.group(1):
        return _clean(text[: m.end(1)])
    # "Bestell(e) / Kauf(e) / Besorg(e) X"
    m = re.search(r"\b(bestell(?:e)?|kauf(?:e)?|besorg(?:e)?)\s+(.+)$", low)
    if m:
        return _clean(text[text.lower().index(m.group(2)):])
    # "Setz X auf die Einkaufsliste" / "Füge X (zur Einkaufsliste) hinzu"
    m = re.search(r"\b(setz(?:e)?|füge?)\s+(.+?)\s+(auf|zur|zum|hinzu|zu)\b.*(einkauf|liste)?", low)
    if m and m.group(2):
        return _clean(text[text.lower().index(m.group(2)): text.lower().index(m.group(2)) + len(m.group(2))])
    return None


def _extract_reminder(text: str) -> Optional[Dict[str, Any]]:
    low = text.lower()
    m = re.search(r"erinnere?\s+mich\s+(.+)$", low)
    if not m:
        m = re.search(r"erinnerung[:\s]+(.+)$", low)
    if not m:
        return None
    rest = text[low.index(m.group(1)):]
    recurrence, rec_due = _parse_recurrence(rest)
    due = rec_due or _parse_when(rest)
    result: Dict[str, Any] = {"title": _reminder_title(rest)}
    if due:
        result["due_at"] = due.isoformat()
    if recurrence != "none":
        result["recurrence"] = recurrence
    return result


def _extract_time(low: str) -> tuple[int, int]:
    m = re.search(r"um\s+(\d{1,2})(?::(\d{2}))?\s*(uhr)?", low)
    if m and (m.group(3) or m.group(2)):
        return int(m.group(1)), int(m.group(2) or 0)
    if "abend" in low:
        return 19, 0
    if "früh" in low or "morgens" in low:
        return 8, 0
    if "mittag" in low:
        return 12, 0
    return 9, 0


def _parse_recurrence(text: str):
    low = text.lower()
    hour, minute = _extract_time(low)
    for name, idx in WEEKDAYS_DE.items():
        if re.search(rf"\bjede[nrs]?\s+{name}", low) or re.search(rf"\b{name}s\b", low):
            return "weekly", next_weekday(idx, hour, minute)
    if re.search(r"werktags|jeden werktag|unter der woche", low):
        due = next_at(hour, minute)
        while due.weekday() >= 5:
            due = next_at(hour, minute, due)
        return "weekdays", due
    if re.search(r"t[äa]glich|jeden tag", low):
        return "daily", next_at(hour, minute)
    if re.search(r"w[öo]chentlich|jede woche", low):
        return "weekly", next_at(hour, minute)
    if re.search(r"monatlich|jeden monat", low):
        return "monthly", next_at(hour, minute)
    return "none", None


def _reminder_title(rest: str) -> str:
    t = rest
    t = re.sub(r"\b(jede[nrs]?\s+)?(montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonnabend|sonntag)s?\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(jeden tag|t[äa]glich|werktags|jeden werktag|unter der woche|w[öo]chentlich|jede woche|monatlich|jeden monat)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\bum\s+\d{1,2}(:\d{2})?\s*uhr\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(heute\s+abend|heute\s+früh|heute|morgen\s+früh|morgen|übermorgen)\s*", "", t.strip(), flags=re.IGNORECASE)
    t = re.sub(r"\b(abends?|morgens|mittags|früh)\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^(an|um|dass|daran,?)\s+", "", t.strip(), flags=re.IGNORECASE)
    t = re.sub(r"^(den|die|das|der)\s+", "", t.strip(), flags=re.IGNORECASE)
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.")
    return t.capitalize() if t else rest.strip().capitalize()


def _extract_task(text: str) -> Optional[str]:
    low = text.lower()
    m = re.search(r"\b(neue\s+aufgabe|aufgabe|to-?do|plane?)[:\s]+(.+)$", low)
    if m:
        return _clean(text[text.lower().index(m.group(2)):])
    return None


def _extract_light_name(text: str) -> str:
    t = re.sub(
        r"\b(mach|schalte?|bitte|kannst du|das|die|der|den|im|in|licht|lampe|lampen|beleuchtung|"
        r"an|aus|ein|anmachen|ausmachen|einschalten|ausschalten)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\s{2,}", " ", t).strip(" ,.")
    return t or "Licht"


def _extract_search(text: str) -> Optional[str]:
    low = text.lower()
    m = re.search(r"\b(such(?:e)?(?:\s+nach)?|finde|wo\s+ist)\s+(.+)$", low)
    if m:
        return _clean(text[text.lower().index(m.group(2)):])
    return None


def _parse_when(text: str) -> Optional[datetime]:
    low = text.lower()
    now = datetime.now()
    today = now.replace(minute=0, second=0, microsecond=0)
    if "heute abend" in low:
        return today.replace(hour=19)
    if "heute früh" in low or "heute morgen" in low:
        return today.replace(hour=8)
    if "heute" in low:
        return today.replace(hour=18)
    if "morgen früh" in low:
        return (today + timedelta(days=1)).replace(hour=8)
    if "übermorgen" in low:
        return (today + timedelta(days=2)).replace(hour=9)
    if "morgen" in low:
        return (today + timedelta(days=1)).replace(hour=9)
    m = re.search(r"um\s+(\d{1,2})(?::(\d{2}))?\s*uhr", low)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        candidate = today.replace(hour=hour, minute=minute)
        if candidate < now:
            candidate += timedelta(days=1)
        return candidate
    return None


def _clean(s: str) -> str:
    s = s.strip().strip(".!?,")
    # Häufige Artikel/Präpositionen am Anfang entfernen
    s = re.sub(r"^(bitte|noch|mal)\s+", "", s, flags=re.IGNORECASE)
    return s.strip()
