"""LLM-Client (OpenAI-kompatibel).

Funktioniert mit OpenAI ebenso wie mit lokalen Modellen (Ollama, LM Studio,
vLLM, GPT-OSS), indem lediglich ``AI_BASE_URL`` angepasst wird. Ist kein
Provider/Key konfiguriert, meldet ``is_configured=False`` und der Agent nutzt
den regelbasierten Fallback.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("ai.llm")


class LLMClient:
    @property
    def is_configured(self) -> bool:
        if not settings.ai_enabled:
            return False
        if settings.ai_provider == "none":
            return False
        # Lokale Provider brauchen ggf. keinen Key.
        if settings.ai_provider == "local":
            return bool(settings.ai_base_url)
        return bool(settings.ai_api_key)

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """Ein Chat-Completion-Aufruf. Gibt die Assistant-Message zurück."""
        if not self.is_configured:
            raise RuntimeError("LLM not configured")

        payload: Dict[str, Any] = {
            "model": settings.ai_model,
            "messages": messages,
            "max_tokens": settings.ai_max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice

        headers = {"Content-Type": "application/json"}
        if settings.ai_api_key:
            headers["Authorization"] = f"Bearer {settings.ai_api_key}"

        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        async with httpx.AsyncClient(timeout=45.0, verify=settings.verify_tls) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]


llm_client = LLMClient()
