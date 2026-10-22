"""UCVE Google Gemini LLM adapter (OpenAI-compatible completions endpoint; mock fallback)."""

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
from core.providers.mode import should_use_mock_provider

logger = get_logger("ucve.providers.gemini")

_DEFAULT_MODEL = "gemini-2.5-flash"
_MODEL_ALIASES: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "default": "gemini-2.5-flash",
    "fast": "gemini-2.5-flash",
    "gemini-2.5": "gemini-2.5-flash",
    "gemini-2.0": "gemini-2.0-flash",
    "gemini-1.5": "gemini-1.5-flash",
}


def resolve_gemini_model(model: str | None) -> str:
    """Map alias or clean model identifier for Gemini API."""
    raw = (model or _DEFAULT_MODEL).strip()
    return _MODEL_ALIASES.get(raw, raw)


def _finalize_tool_calls(tool_acc: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """Build finalized tool-call dicts from accumulated stream fragments."""
    calls: list[dict[str, Any]] = []
    for _idx in sorted(tool_acc):
        slot = tool_acc[_idx]
        raw_args = slot.get("arguments") or ""
        try:
            parsed = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            parsed = {"_raw": raw_args}
        calls.append(
            {
                "id": slot.get("id"),
                "name": slot.get("name", ""),
                "arguments": parsed,
            }
        )
    return calls


class GeminiLLMProvider(BaseLLMProvider):
    """Google Gemini LLM provider via OpenAI-compatible endpoint."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.default_model = resolve_gemini_model(model or _DEFAULT_MODEL)
        self._base = "https://generativelanguage.googleapis.com/v1beta/openai"
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

        use_mock = should_use_mock_provider(
            provider_id="gemini", api_key=self.api_key
        )
        if use_mock:
            if not self.api_key:
                logger.info("Gemini API key not set — using Mock LLM provider.")
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

        model_name = resolve_gemini_model(config.model or self.default_model)
        client = self._get_client()
        request_body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "stream": True,
        }
        if config.tools:
            request_body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters or {"type": "object", "properties": {}},
                    },
                }
                for t in config.tools
            ]
            request_body["tool_choice"] = "auto"

        tool_acc: dict[int, dict[str, Any]] = {}
        try:
            logger.info("Initiating Gemini LLM completion stream", model=model_name)
            async with client.stream(
                "POST",
                f"{self._base}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request_body,
            ) as resp:
                if resp.status_code != 200:
                    await resp.aread()
                    logger.error(
                        "Gemini API call failed",
                        status_code=resp.status_code,
                    )
                    raise ProviderInvocationError(
                        classify_http_failure("gemini", resp.status_code)
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

                    for frag in delta.get("tool_calls", []) or []:
                        idx = frag.get("index", 0)
                        slot = tool_acc.setdefault(
                            idx, {"id": None, "name": "", "arguments": ""}
                        )
                        if frag.get("id"):
                            slot["id"] = frag["id"]
                        fn = frag.get("function", {}) or {}
                        if fn.get("name"):
                            slot["name"] = fn["name"]
                        if fn.get("arguments"):
                            slot["arguments"] += fn["arguments"]

                    text = delta.get("content") or ""
                    if text:
                        yield LLMStreamChunk(
                            text=text,
                            is_first_token=first,
                            finish_reason=finish_reason,
                        )
                        first = False

                    if finish_reason == "tool_calls" and tool_acc:
                        yield LLMStreamChunk(
                            tool_calls=_finalize_tool_calls(tool_acc),
                            finish_reason="tool_calls",
                        )
                        tool_acc.clear()
        except ProviderInvocationError:
            await self.aclose()
            raise
        except Exception as exc:
            logger.error("Gemini stream exception", error_type=type(exc).__name__)
            await self.aclose()
            raise provider_invocation_error("gemini", exc) from exc
