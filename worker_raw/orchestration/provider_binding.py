"""Bind authenticated session-plan routes to session-owned provider adapters."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol

from core.listening.config import SpeakingPipelineConfig
from core.providers.routing import ProviderRouteBuilder, ResolvedProviderRoute
from core.secrets.vault import SecretVault
from worker_raw.orchestration.session_config import PipelineSessionConfig


class RouteBuilder(Protocol):
    def build_chain(
        self, tenant_id: str, category: str, language: str, routes: tuple
    ) -> tuple[ResolvedProviderRoute, ...]: ...


@dataclass(slots=True)
class BoundProviderChains:
    stt: tuple[ResolvedProviderRoute, ...]
    llm: tuple[ResolvedProviderRoute, ...]
    tts: tuple[ResolvedProviderRoute, ...]
    _closed: bool = field(default=False, init=False, repr=False)

    @property
    def all_routes(self) -> tuple[ResolvedProviderRoute, ...]:
        return self.stt + self.llm + self.tts

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        seen: set[int] = set()
        for route in self.all_routes:
            adapter = route.adapter
            if id(adapter) in seen:
                continue
            seen.add(id(adapter))
            close = getattr(adapter, "aclose", None)
            if close is None:
                continue
            result = close()
            if asyncio.iscoroutine(result):
                await result


class ProviderSessionBinder:
    """Resolve and construct all published routes as one startup transaction."""

    def __init__(self, route_builder: RouteBuilder) -> None:
        self.route_builder = route_builder

    @classmethod
    def default(
        cls,
        *,
        speaking_config: SpeakingPipelineConfig | None = None,
        stt_mock_text: str = "",
    ) -> ProviderSessionBinder:
        return cls(
            ProviderRouteBuilder(
                SecretVault(),
                speaking_config=speaking_config,
                stt_mock_text=stt_mock_text,
            )
        )

    async def bind(self, config: PipelineSessionConfig) -> BoundProviderChains:
        built: dict[str, tuple[ResolvedProviderRoute, ...]] = {}
        try:
            for category in ("stt", "llm", "tts"):
                built[category] = self.route_builder.build_chain(
                    config.tenant_id,
                    category,
                    config.language,
                    config.runtime_provider_routes(category),
                )
        except Exception:
            partial = BoundProviderChains(
                stt=built.get("stt", ()),
                llm=built.get("llm", ()),
                tts=built.get("tts", ()),
            )
            await partial.aclose()
            raise
        return BoundProviderChains(
            stt=built["stt"],
            llm=built["llm"],
            tts=built["tts"],
        )
