from __future__ import annotations

import json

import httpx
import pytest

from core.providers.adapters.openai_llm import OpenAILLMProvider
from core.providers.interfaces.llm import LLMConfig


@pytest.mark.asyncio
async def test_openai_stream_emits_exact_provider_usage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RUN_MOCK_PROVIDERS", "0")
    monkeypatch.setenv("RUN_LIVE_PROVIDERS", "1")
    captured_payload: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content))
        stream = (
            'data: {"id":"request-a","choices":[{"delta":{"content":"Hi"},'
            '"finish_reason":null}]}\n\n'
            'data: {"id":"request-a","choices":[{"delta":{},'
            '"finish_reason":"stop"}]}\n\n'
            'data: {"id":"request-a","choices":[],"usage":'
            '{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\n'
            "data: [DONE]\n\n"
        )
        return httpx.Response(
            200,
            content=stream.encode(),
            headers={"content-type": "text/event-stream"},
        )

    provider = OpenAILLMProvider(api_key="offline-test-value")
    provider._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    try:
        chunks = [
            chunk
            async for chunk in provider.generate_stream(
                [{"role": "user", "content": "hello"}],
                LLMConfig(model="gpt-4o-mini"),
            )
        ]
    finally:
        await provider.aclose()

    assert captured_payload["stream_options"] == {"include_usage": True}
    usage = next(chunk for chunk in chunks if chunk.total_tokens is not None)
    assert usage.prompt_tokens == 10
    assert usage.completion_tokens == 5
    assert usage.total_tokens == 15
    assert usage.provider_id == "openai"
    assert usage.provider_request_id == "request-a"
