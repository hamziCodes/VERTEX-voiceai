"""UCVE OpenAI LLM adapter (chat completions streaming; mock fallback without API key)."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import httpx

from core.buffers.cancellation import CancellationToken
from core.observability.logging import get_logger
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk

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


class OpenAILLMProvider(BaseLLMProvider):
    """OpenAI chat completions provider with streaming and cancellation."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = (
            api_key
            or os.environ.get("PLATFORM_OPENAI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or ""
        ).strip()
        self.default_model = resolve_openai_model(model or _DEFAULT_MODEL)
        self.model = self.default_model
        self._url = "https://api.openai.com/v1/chat/completions"
        self._client: httpx.AsyncClient | None = None

    def health_check(self) -> bool:
        return True

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
        use_mock = (
            not self.api_key
            or os.environ.get("RUN_MOCK_PROVIDERS") == "1"
            or os.environ.get("RUN_LIVE_PROVIDERS") != "1"
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
            payload["tools"] = config.tools
            if config.tool_choice:
                payload["tool_choice"] = config.tool_choice

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        client = self._get_client()
        tool_acc: dict[int, dict[str, Any]] = {}

        first = True
        try:
            async with client.stream("POST", self._url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    logger.error("OpenAI stream error", status=resp.status_code, body=body.decode(errors="replace")[:300])
                    async for chunk in self._mock_stream(messages, cancellation_token):
                        yield chunk
                    return

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
                        idx = int(tc.get("index", 0))
                        slot = tool_acc.setdefault(idx, {})
                        if tc.get("id"):
                            slot["id"] = tc["id"]
                        fn = tc.get("function") or {}
                        if fn.get("name"):
                            slot["name"] = (slot.get("name") or "") + fn["name"]
                        if fn.get("arguments"):
                            slot["arguments"] = (slot.get("arguments") or "") + fn["arguments"]

                    text = delta.get("content")
                    finish = choices[0].get("finish_reason")
                    if text:
                        yield LLMStreamChunk(text=text, is_first_token=first, finish_reason=finish)
                        first = False

                    if finish:
                        calls = _finalize_tool_calls(tool_acc) if tool_acc else None
                        if calls:
                            yield LLMStreamChunk(tool_calls=calls, finish_reason=finish)
                        return

            if tool_acc:
                calls = _finalize_tool_calls(tool_acc)
                yield LLMStreamChunk(tool_calls=calls, finish_reason="tool_calls")

        except Exception as exc:
            logger.error("OpenAI stream exception", error=str(exc))
            async for chunk in self._mock_stream(messages, cancellation_token):
                yield chunk

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
