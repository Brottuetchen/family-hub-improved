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
from app.ai.tools import TOOLS, ToolContext, openai_tools
from app.core.logging_config import get_logger

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
    ctx = ToolContext(db=db, user_id=user_id)
    if llm_client.is_configured:
        try:
            return await _run_llm(message, ctx, history or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM agent failed, falling back to rules: %s", exc)
    return await _run_rules(message, ctx)


async def _execute_tool(name: str, ctx: ToolContext, args: Dict[str, Any]) -> str:
    tool = TOOLS.get(name)
    if not tool:
        return f"Unbekanntes Werkzeug: {name}"
    try:
        return await tool.handler(ctx, **args)
    except TypeError as exc:
        return f"Ungültige Parameter für {name}: {exc}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("tool %s failed: %s", name, exc)
        return f"Fehler bei {name}: {exc}"


async def _run_llm(message: str, ctx: ToolContext, history: List[Dict[str, str]]) -> Dict[str, Any]:
    messages: List[Dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})

    executed: List[str] = []
    for _ in range(MAX_ITERATIONS):
        msg = await llm_client.chat(messages, tools=openai_tools())
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
    rest = text[text.lower().index(m.group(1)):]
    due = _parse_when(rest)
    # "an den Müll" -> Müll
    title = re.sub(r"^(heute\s+abend|heute\s+früh|heute|morgen\s+früh|morgen|übermorgen)\s*", "", rest, flags=re.IGNORECASE)
    title = re.sub(r"^(an|um|dass|daran,?)\s+", "", title, flags=re.IGNORECASE).strip()
    title = re.sub(r"^(den|die|das|der)\s+", "", title, flags=re.IGNORECASE).strip()
    if not title:
        title = rest.strip()
    result: Dict[str, Any] = {"title": title.capitalize()}
    if due:
        result["due_at"] = due.isoformat()
    return result


def _extract_task(text: str) -> Optional[str]:
    low = text.lower()
    m = re.search(r"\b(neue\s+aufgabe|aufgabe|to-?do|plane?)[:\s]+(.+)$", low)
    if m:
        return _clean(text[text.lower().index(m.group(2)):])
    return None


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
