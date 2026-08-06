"""Aufgaben-Connector für Vikunja (https://vikunja.io).

Vikunja ist das führende System für Aufgaben/Projekte. Hermes liest offene
Aufgaben, zeigt Fälligkeiten im Dashboard und kann via KI neue Aufgaben anlegen.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class VikunjaConnector(BaseConnector):
    name = "vikunja"
    display_name = "Aufgaben (Vikunja)"
    category = "tasks"
    icon = "✅"

    @property
    def is_configured(self) -> bool:
        return bool(settings.vikunja_url and settings.vikunja_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.vikunja_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {settings.vikunja_token}"}

    async def _probe(self) -> bool:
        # /api/v1/tasks/all statt /api/v1/user: dauerhafte API-Tokens dürfen die
        # User-Route nicht, wohl aber die Aufgaben-Route – so ist die Health-Prüfung
        # sowohl mit API-Token als auch mit JWT grün.
        await self._get_json("/api/v1/tasks/all", params={"per_page": 1})
        return True

    async def get_tasks(self, include_done: bool = False, limit: int = 50) -> List[Dict[str, Any]]:
        """Liefert Aufgaben (standardmäßig nur offene)."""
        if not self.is_configured:
            return []
        try:
            raw = await self._get_json(
                "/api/v1/tasks/all",
                params={"sort_by": "due_date", "order_by": "asc", "per_page": limit},
            )
            tasks = raw if isinstance(raw, list) else []
            out: List[Dict[str, Any]] = []
            for t in tasks:
                if not include_done and t.get("done"):
                    continue
                out.append(_normalize_task(t, settings.vikunja_url))
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("vikunja get_tasks failed: %s", exc)
            return []

    async def create_task(
        self, title: str, description: str = "", due_date: Optional[str] = None,
        priority: Optional[int] = None, project_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Legt eine neue Aufgabe an (in einem Projekt)."""
        if not self.is_configured:
            return None
        try:
            if project_id is None:
                projects = await self._get_json("/api/v1/projects")
                if isinstance(projects, list) and projects:
                    project_id = projects[0].get("id")
            if project_id is None:
                self.logger.warning("vikunja create_task: no project found")
                return None

            payload: Dict[str, Any] = {"title": title}
            if description:
                payload["description"] = description
            if due_date:
                payload["due_date"] = due_date
            if priority is not None:
                payload["priority"] = priority

            async with self._client() as client:
                resp = await client.put(f"/api/v1/projects/{project_id}/tasks", json=payload)
                resp.raise_for_status()
                return _normalize_task(resp.json(), settings.vikunja_url)
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("vikunja create_task failed: %s", exc)
            return None

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            raw = await self._get_json("/api/v1/tasks/all", params={"s": query, "per_page": limit})
            tasks = raw if isinstance(raw, list) else []
            return [
                {
                    "title": t.get("title", "Aufgabe"),
                    "subtitle": "Erledigt" if t.get("done") else "Offen",
                    "url": f"{(settings.vikunja_url or '').rstrip('/')}/tasks/{t.get('id')}",
                    "source": self.display_name,
                    "category": self.category,
                    "icon": self.icon,
                }
                for t in tasks[:limit]
            ]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("vikunja search failed: %s", exc)
            return []


def _normalize_task(t: Dict[str, Any], base: Optional[str]) -> Dict[str, Any]:
    return {
        "id": t.get("id"),
        "title": t.get("title", "Aufgabe"),
        "description": t.get("description", ""),
        "done": bool(t.get("done")),
        "due_date": t.get("due_date"),
        "priority": t.get("priority", 0),
        "url": f"{(base or '').rstrip('/')}/tasks/{t.get('id')}" if base else None,
    }
