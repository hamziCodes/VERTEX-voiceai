"""LLM provider factory and adapter smoke tests (no network)."""

from __future__ import annotations

import os
import pytest

from core.buffers.cancellation import AsyncioCancellationToken
from core.providers.adapters.gemini_llm import GeminiLLMProvider, resolve_gemini_model
from core.providers.adapters.groq_llm import GroqLLMProvider, resolve_groq_model
from core.providers.factory import build_llm_provider, normalize_llm_provider
from core.providers.interfaces.llm import LLMConfig
from core.providers.registry import ProviderRegistry
import worker_raw.orchestration.pipeline  # noqa: F401


def test_normalize_llm_provider_defaults_and_allows_vendors() -> None:
    assert normalize_llm_provider(None) == "groq"
    assert normalize_llm_provider("GROQ") == "groq"
    assert normalize_llm_provider("gemini") == "gemini"
    assert normalize_llm_provider("GEMINI") == "gemini"
    assert normalize_llm_provider("unknown") == "groq"


def test_build_llm_provider_switches() -> None:
    groq = build_llm_provider("groq", model="openai/gpt-oss-120b")
    assert isinstance(groq, GroqLLMProvider)
    assert groq.default_model == "openai/gpt-oss-120b"

    gemini = build_llm_provider("gemini", model="gemini-2.5-flash")
    assert isinstance(gemini, GeminiLLMProvider)
    assert gemini.default_model == "gemini-2.5-flash"


def test_gemini_model_resolution() -> None:
    assert resolve_gemini_model("gemini-2.5-flash") == "gemini-2.5-flash"
    assert resolve_gemini_model("gemini") == "gemini-2.5-flash"
    assert resolve_gemini_model("default") == "gemini-2.5-flash"
    assert resolve_gemini_model("gemini-2.0") == "gemini-2.0-flash"


def test_groq_model_resolution() -> None:
    assert resolve_groq_model("openai/gpt-oss-120b") == "openai/gpt-oss-120b"
    assert resolve_groq_model("openai/gpt-oss-20b") == "openai/gpt-oss-20b"
    assert resolve_groq_model("qwen/qwen3.8-27b") == "qwen/qwen3.8-27b"
    assert resolve_groq_model("llama-3.3-70b-versatile") == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_gemini_mock_stream_without_live_flag() -> None:
    os.environ.pop("RUN_LIVE_PROVIDERS", None)
    provider = GeminiLLMProvider(api_key="")
    chunks = []
    messages = [{"role": "user", "content": "Tell me a joke."}]
    async for chunk in provider.generate_stream(messages, LLMConfig(model="gemini-2.5-flash")):
        chunks.append(chunk)
    assert len(chunks) > 0
    assert any(c.is_first_token for c in chunks)
    text = "".join(c.text for c in chunks)
    assert "Mock reply" in text


@pytest.mark.asyncio
async def test_gemini_cancellation_token() -> None:
    os.environ.pop("RUN_LIVE_PROVIDERS", None)
    provider = GeminiLLMProvider(api_key="")
    token = AsyncioCancellationToken()
    token.cancel()
    chunks = []
    messages = [{"role": "user", "content": "Hello"}]
    async for chunk in provider.generate_stream(
        messages, LLMConfig(model="gemini-2.5-flash"), cancellation_token=token
    ):
        chunks.append(chunk)
    assert len(chunks) == 0


def test_provider_registry_contains_gemini() -> None:
    cls = ProviderRegistry.get_provider_class("gemini")
    assert cls is GeminiLLMProvider

