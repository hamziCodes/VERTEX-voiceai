"""UCVE OpenAI LLM adapter (chat completions streaming; mock fallback without API key)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.exceptions import (
    ProviderInvocationError,
    classify_http_failure,
    provider_invocation_error,
)
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk
from core.providers.mode import provider_is_locally_ready, should_use_mock_provider
from core.providers.tool_calls import ToolCallAccumulator, serialize_tool_definitions

logger = get_logger("ucve.providers.openai")

_DEFAULT_MODEL = "gpt-4o-mini"
_MODEL_ALIASES: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "default": "gpt-4o-mini",
    "fast": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "chatgpt-4o-latest": "gpt-4o",
    "gpt-3.5-turbo": "gpt-4o-mini",
}


def resolve_openai_model(model: str | None) -> str:
    """Map alias or clean model identifier for OpenAI API."""
    raw = (model or _DEFAULT_MODEL).strip()
    return _MODEL_ALIASES.get(raw, raw)


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI chat completions provider with streaming and cancellation."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.default_model = resolve_openai_model(model or _DEFAULT_MODEL)
        self.model = self.default_model
        self._url = "https://api.openai.com/v1/chat/completions"
        self._client: httpx.AsyncClient | None = None

    def health_check(self) -> bool:
        return provider_is_locally_ready(api_key=self.api_key)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0))
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        use_mock = should_use_mock_provider(
            provider_id="openai", api_key=self.api_key
        )
        if use_mock:
            async for chunk in self._mock_stream(messages, cancellation_token):
                yield chunk
            return

        payload: dict[str, Any] = {
            "model": resolve_openai_model(config.model or self.model),
            "messages": messages,
            "temperature": float(config.temperature),
            "max_tokens": int(config.max_tokens or 256),
            "stream": True,
        }
        if config.tools:
            payload["tools"] = serialize_tool_definitions(config.tools)
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        tool_acc = ToolCallAccumulator("openai")

        first = True
        try:
            async with client.stream("POST", self._url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    logger.error("OpenAI stream error", status=resp.status_code)
                    raise ProviderInvocationError(
                        classify_http_failure("openai", resp.status_code)
                    )

                async for line in resp.aiter_lines():
                    if cancellation_token and cancellation_token.is_cancelled:
                        return
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data_str = line[5:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}

                    for tc in delta.get("tool_calls") or []:
                        tool_acc.add(tc)

                    text = delta.get("content")
                    finish = choices[0].get("finish_reason")
                    if text:
                        yield LLMStreamChunk(text=text, is_first_token=first, finish_reason=finish)
                        first = False

                    if finish:
                        calls = tool_acc.finalize() if tool_acc else None
                        if calls:
                            yield LLMStreamChunk(tool_calls=calls, finish_reason=finish)
                        return

            if tool_acc:
                calls = tool_acc.finalize()
                yield LLMStreamChunk(tool_calls=calls, finish_reason="tool_calls")

        except ProviderInvocationError:
            raise
        except Exception as exc:
            logger.error("OpenAI stream exception", error_type=type(exc).__name__)
            raise provider_invocation_error("openai", exc) from exc

    async def _mock_stream(
        self,
        messages: list[dict[str, Any]],
        cancellation_token: CancellationToken | None,
    ) -> AsyncIterator[LLMStreamChunk]:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = str(m.get("content") or "")
                break
        reply = f"Understood. {last_user}".strip() if last_user else "I am here to assist you."
        tokens = reply.split()
        for i, word in enumerate(tokens):
            if cancellation_token and cancellation_token.is_cancelled:
                return
            yield LLMStreamChunk(
                text=word + " ",
                is_first_token=(i == 0),
                finish_reason="stop" if i == len(tokens) - 1 else None,
            )
