"""UCVE Groq LLM adapter (chat completions; mock mode without API key)."""

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

logger = get_logger("ucve.providers.groq")

_DEFAULT_MODEL = "openai/gpt-oss-120b"
_MODEL_ALIASES: dict[str, str] = {
    "openai/gpt-oss-120b": "openai/gpt-oss-120b",
    "openai/gpt-oss-20b": "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b": "qwen/qwen3.8-27b",
    "qwen3.8-27b": "qwen/qwen3.8-27b",
    "llama-3.1-8b-instant": "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama3-8b-8192": "openai/gpt-oss-120b",
    "default": "openai/gpt-oss-120b",
    "fast": "openai/gpt-oss-120b",
}


def resolve_groq_model(model: str | None) -> str:
    """Map deprecated/unknown model ids to a current Groq model."""
    raw = (model or _DEFAULT_MODEL).strip()
    return _MODEL_ALIASES.get(raw, raw)


class GroqLLMProvider(BaseLLMProvider):
    """Groq OpenAI-compatible chat API. Mocks when GROQ_API_KEY unset."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.default_model = resolve_groq_model(model or _DEFAULT_MODEL)
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
        return provider_is_locally_ready(api_key=self.api_key)

    async def generate_stream(
        self,
        messages: list[dict[str, Any]],
        config: LLMConfig,
        cancellation_token: CancellationToken | None = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        if cancellation_token and cancellation_token.is_cancelled:
            return

        use_mock = should_use_mock_provider(provider_id="groq", api_key=self.api_key)
        if use_mock:
            if not self.api_key:
                logger.info("Groq API key not set — using Mock LLM provider.")
            user = next(
                (m["content"] for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
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
        request_body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if config.tools:
            request_body["tools"] = serialize_tool_definitions(config.tools)
            request_body["tool_choice"] = "auto"
        # Accumulates streamed tool-call fragments keyed by choice index.
        tool_acc = ToolCallAccumulator("groq")
        try:
            logger.info("Initiating Groq LLM completion stream", model=model_name)
            async with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body,
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    logger.error(
                        "Groq API call failed",
                        status_code=resp.status_code,
                    )
                    raise ProviderInvocationError(
                        classify_http_failure("groq", resp.status_code)
                    )
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
                    choice = data.get("choices", [{}])[0]
                    delta = choice.get("delta", {})
                    finish_reason = choice.get("finish_reason")

                    # Accumulate streamed tool-call fragments.
                    for frag in delta.get("tool_calls", []) or []:
                        tool_acc.add(frag)

                    text = delta.get("content") or ""
                    if text:
                        yield LLMStreamChunk(
                            text=text,
                            is_first_token=first,
                            finish_reason=finish_reason,
                        )
                        first = False

                    if finish_reason and tool_acc:
                        yield LLMStreamChunk(
                            tool_calls=tool_acc.finalize(),
                            finish_reason=finish_reason,
                        )
                        tool_acc.clear()
                if tool_acc:
                    yield LLMStreamChunk(
                        tool_calls=tool_acc.finalize(),
                        finish_reason="tool_calls",
                    )
        except ProviderInvocationError:
            await self.aclose()
            raise
        except Exception as exc:
            logger.error("Groq stream exception", error_type=type(exc).__name__)
            await self.aclose()
            raise provider_invocation_error("groq", exc) from exc
