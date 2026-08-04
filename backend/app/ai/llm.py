"""LLM-Transport (OpenAI-kompatibel) – Relay zum hermes-agent-Sidecar.

Der ``Assistent"-Chat spricht ausschließlich den echten NousResearch/hermes-agent
an (``AI_PROVIDER=hermes_agent``): Er ist selbst der Agent (Tools/Skills/Memory)
und steuert unsere Module via MCP. Wir **relayen** nur Chat/Streaming/Voice an
seinen OpenAI-kompatiblen API-Server und injizieren **keine** eigenen
Tool-Schemas.

Ist kein Sidecar konfiguriert, meldet ``is_configured=False`` und der Chat gibt
einen klaren „nicht verbunden"-Hinweis (kein Wort-Matcher, kein eigener Agent).
"""

from __future__ import annotations

import json
import time
from typing import Any, AsyncIterator, Dict, List, Optional

import httpx

from app.config import settings
from app.core.logging_config import get_logger

logger = get_logger("ai.llm")


class LLMClient:
    def __init__(self) -> None:
        self._ping_ts: float = 0.0
        self._ping_ok: bool = False

    # --- Modus/Backend ---

    @property
    def provider(self) -> str:
        return settings.ai_provider

    @property
    def is_agentic(self) -> bool:
        """True, wenn der externe hermes-agent das Gehirn ist (kein eigener Tool-Loop)."""
        return settings.ai_provider == "hermes_agent"

    @property
    def is_configured(self) -> bool:
        if not settings.ai_enabled:
            return False
        if settings.ai_provider == "none":
            return False
        if settings.ai_provider == "hermes_agent":
            return bool(settings.hermes_agent_url)
        if settings.ai_provider == "local":
            return bool(settings.ai_base_url)
        return bool(settings.ai_api_key)

    @property
    def model(self) -> str:
        return settings.hermes_agent_model if self.is_agentic else settings.ai_model

    def _base_url(self) -> str:
        raw = settings.hermes_agent_url if self.is_agentic else settings.ai_base_url
        return (raw or "").rstrip("/")

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.is_agentic:
            if settings.hermes_agent_token:
                headers["Authorization"] = f"Bearer {settings.hermes_agent_token}"
        elif settings.ai_api_key:
            headers["Authorization"] = f"Bearer {settings.ai_api_key}"
        return headers

    async def ping(self, ttl: float = 5.0) -> bool:
        """Kurzer Reachability-Check gegen den Sidecar (GET /models), gecacht.

        Liefert True nur, wenn der API-Server wirklich antwortet – damit der
        Status „verbunden" die echte Erreichbarkeit zeigt, nicht nur die Config.
        """
        if not self.is_configured:
            return False
        now = time.monotonic()
        if now - self._ping_ts < ttl:
            return self._ping_ok
        headers = {}
        auth = self._headers().get("Authorization")
        if auth:
            headers["Authorization"] = auth
        ok = False
        try:
            async with httpx.AsyncClient(timeout=2.0, verify=settings.verify_tls) as client:
                resp = await client.get(f"{self._base_url()}/models", headers=headers)
                ok = resp.status_code < 400
        except Exception:  # noqa: BLE001
            ok = False
        self._ping_ts, self._ping_ok = now, ok
        return ok

    def _payload(self, messages: List[Dict[str, Any]], tools, tool_choice, stream: bool) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": settings.ai_max_tokens,
        }
        if stream:
            payload["stream"] = True
        # Im Agentic-Modus KEINE Tools injizieren – der Sidecar ist der Agent.
        if tools and not self.is_agentic:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice
        return payload

    # --- Nicht-Streaming ---

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> Dict[str, Any]:
        """Ein Chat-Completion-Aufruf. Gibt die Assistant-Message zurück."""
        if not self.is_configured:
            raise RuntimeError("LLM not configured")
        payload = self._payload(messages, tools, tool_choice, stream=False)
        url = f"{self._base_url()}/chat/completions"
        async with httpx.AsyncClient(timeout=120.0, verify=settings.verify_tls) as client:
            resp = await client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()
        return data["choices"][0]["message"]

    # --- Streaming (SSE) ---

    # --- Sprach-Transkription (Voice-Messages) ---

    async def transcribe(self, content: bytes, filename: str, content_type: str) -> str:
        """Transkribiert Audio über einen OpenAI-/Whisper-kompatiblen Endpoint.

        Nutzt den hermes-agent-Sidecar (agentic) bzw. das konfigurierte Modell.
        """
        if not self.is_configured:
            raise RuntimeError("LLM not configured")
        url = f"{self._base_url()}/audio/transcriptions"
        headers = {}
        auth = self._headers().get("Authorization")
        if auth:
            headers["Authorization"] = auth
        files = {"file": (filename or "audio.webm", content, content_type or "audio/webm")}
        data = {"model": settings.ai_transcribe_model}
        async with httpx.AsyncClient(timeout=120.0, verify=settings.verify_tls) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
            resp.raise_for_status()
            payload = resp.json()
        return (payload.get("text") or "").strip()

    async def stream_chat(self, messages: List[Dict[str, Any]]) -> AsyncIterator[str]:
        """Streamt die Antwort-Tokens (Content-Deltas) eines Chat-Completions-Aufrufs.

        Für den Agentic-/Relay-Modus (hermes-agent) sowie direkte Modelle nutzbar.
        Yields die reinen Text-Deltas.
        """
        if not self.is_configured:
            raise RuntimeError("LLM not configured")
        payload = self._payload(messages, tools=None, tool_choice="auto", stream=True)
        url = f"{self._base_url()}/chat/completions"
        async with httpx.AsyncClient(timeout=None, verify=settings.verify_tls) as client:
            async with client.stream("POST", url, json=payload, headers=self._headers()) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        yield text


llm_client = LLMClient()
