"""UCVE Groq LLM adapter (chat completions; mock mode without API key)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk


from core.observability.logging import get_logger

logger = get_logger("ucve.providers.groq")

_DEFAULT_MODEL = "llama-3.3-70b-versatile"
_MODEL_ALIASES: dict[str, str] = {
    "llama-3.1-8b-instant": _DEFAULT_MODEL,
    "llama3-8b-8192": _DEFAULT_MODEL,
    "default": _DEFAULT_MODEL,
}


def resolve_groq_model(model: str | None) -> str:
    """Map deprecated/unknown model ids to a current Groq model."""
    raw = (model or _DEFAULT_MODEL).strip()
    return _MODEL_ALIASES.get(raw, raw)


class GroqLLMProvider(BaseLLMProvider):
    """Groq OpenAI-compatible chat API. Mocks when GROQ_API_KEY unset."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_GROQ_API_KEY")
            or os.environ.get("GROQ_API_KEY")
            or ""
        ).strip()
        self._base = "https://api.groq.com/openai/v1"
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

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

        use_mock = (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
        )
        if use_mock:
            if not self.api_key:
                logger.info("Groq API key not set — using Mock LLM provider.")
            user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            reply = f"Mock reply to: {user}" if user else "Mock reply"
            for i, word in enumerate(reply.split()):
                if cancellation_token and cancellation_token.is_cancelled:
                    return
                yield LLMStreamChunk(
                    text=word + (" " if i < len(reply.split()) - 1 else ""),
                    is_first_token=(i == 0),
                    finish_reason="stop" if i == len(reply.split()) - 1 else None,
                )
            return

        model_name = resolve_groq_model(config.model)
        client = self._get_client()
        try:
            logger.info("Initiating Groq LLM completion stream", model=model_name)
            async with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": model_name,
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                    "stream": True,
                },
            ) as resp:
                if resp.status_code != 200:
                    err_body = await resp.aread()
                    logger.error(
                        "Groq API call failed",
                        status_code=resp.status_code,
                        error=err_body.decode(errors="ignore"),
                    )
                    resp.raise_for_status()
                first = True
                async for line in resp.aiter_lines():
                    if cancellation_token and cancellation_token.is_cancelled:
                        await resp.aclose()
                        return
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:].strip()
                    if payload == "[DONE]":
                        break
                    data = json.loads(payload)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    text = delta.get("content") or ""
                    if text:
                        yield LLMStreamChunk(
                            text=text,
                            is_first_token=first,
                            finish_reason=data.get("choices", [{}])[0].get("finish_reason"),
                        )
                        first = False
        except httpx.HTTPStatusError as exc:
            logger.error(f"Groq HTTP Error: {exc}", error=str(exc))
            await self.aclose()
            raise
        except Exception as exc:
            logger.error(f"Groq Stream Exception: {exc}", error=str(exc))
            await self.aclose()
            raise
