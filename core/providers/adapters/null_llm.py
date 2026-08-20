"""UCVE Null LLM Test Adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from core.buffers.cancellation import CancellationToken
from core.providers.interfaces.llm import BaseLLMProvider, LLMConfig, LLMStreamChunk


class NullLLMProvider(BaseLLMProvider):
    """No-op LLM provider implementation for testing."""

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
        yield LLMStreamChunk(text="", finish_reason="stop", is_first_token=True)
