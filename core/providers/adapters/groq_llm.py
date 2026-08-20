"""UCVE Groq LLM adapter (chat completions; mock mode without API key)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk


class GroqLLMProvider(BaseLLMProvider):
    """Groq OpenAI-compatible chat API. Mocks when PLATFORM_GROQ_API_KEY unset."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or os.environ.get("PLATFORM_GROQ_API_KEY") or "").strip()
        self._base = "https://api.groq.com/openai/v1"

    def health_check(self) -> bool:
        return True

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        if not self.api_key or os.environ.get("RUN_LIVE_PROVIDERS") != "1":
            user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            reply = f"Mock reply to: {user}" if user else "Mock reply"
            yield LLMStreamChunk(text=reply, is_first_token=True, finish_reason="stop")
            return

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": config.model or "llama-3.1-8b-instant",
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            yield LLMStreamChunk(text=text, is_first_token=True, finish_reason="stop")
