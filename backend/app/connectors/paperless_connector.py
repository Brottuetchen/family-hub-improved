"""Dokumenten-Connector für Paperless-ngx (https://docs.paperless-ngx.com).

Hermes zeigt Rechnungen, Versicherungen, Garantien und Verträge und erkennt
Fristen/Kündigungstermine (via Tags/Custom Fields, sofern in Paperless gepflegt).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.config import settings
from app.connectors.base import BaseConnector


class PaperlessConnector(BaseConnector):
    name = "paperless"
    display_name = "Dokumente (Paperless)"
    category = "documents"
    icon = "📄"

    @property
    def is_configured(self) -> bool:
        return bool(settings.paperless_url and settings.paperless_token)

    @property
    def base_url(self) -> Optional[str]:
        return settings.paperless_url

    def _auth_headers(self) -> Dict[str, str]:
        return {"Authorization": f"Token {settings.paperless_token}"}

    async def _probe(self) -> bool:
        await self._get_json("/api/documents/", params={"page_size": 1})
        return True

    def _doc_url(self, doc_id: Any) -> Optional[str]:
        if not settings.paperless_url:
            return None
        return f"{settings.paperless_url.rstrip('/')}/documents/{doc_id}/"

    async def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Zuletzt hinzugefügte Dokumente."""
        if not self.is_configured:
            return []
        try:
            data = await self._get_json(
                "/api/documents/", params={"ordering": "-created", "page_size": limit}
            )
            results = data.get("results", []) if isinstance(data, dict) else []
            return [self._normalize(d) for d in results]
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("paperless get_recent failed: %s", exc)
            return []

    # Schlüsselwörter, die auf Fristen/Kündigungstermine hindeuten.
    DEADLINE_KEYWORDS = ("kündigung", "frist", "ablauf", "vertrag", "versicherung", "garantie", "police")

    async def get_deadlines(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Best-effort-Erkennung fristrelevanter Dokumente (per Titel-Schlüsselwörtern)."""
        if not self.is_configured:
            return []
        docs = await self.get_recent(limit=50)
        out = []
        for d in docs:
            title = (d.get("title") or "").lower()
            if any(k in title for k in self.DEADLINE_KEYWORDS):
                out.append(d)
        return out[:limit]

    async def search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        if not self.is_configured:
            return []
        try:
            data = await self._get_json(
                "/api/documents/", params={"query": query, "page_size": limit}
            )
            results = data.get("results", []) if isinstance(data, dict) else []
            out = []
            for d in results[:limit]:
                out.append(
                    {
                        "title": d.get("title", "Dokument"),
                        "subtitle": d.get("created_date") or "",
                        "url": self._doc_url(d.get("id")),
                        "source": self.display_name,
                        "category": self.category,
                        "icon": self.icon,
                    }
                )
            return out
        except Exception as exc:  # noqa: BLE001
            self.logger.warning("paperless search failed: %s", exc)
            return []

    def _normalize(self, d: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": d.get("id"),
            "title": d.get("title", "Dokument"),
            "created": d.get("created_date") or d.get("created"),
            "tags": d.get("tags", []),
            "correspondent": d.get("correspondent"),
            "url": self._doc_url(d.get("id")),
        }
