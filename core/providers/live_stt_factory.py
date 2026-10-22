"""Provider-selected factory for warm streaming-STT sessions."""

from __future__ import annotations

from collections.abc import Callable

from core.providers.adapters.gladia_live_stt import GladiaLiveSTTSession
from core.providers.interfaces.live_stt import BaseLiveSTTSession

LiveSTTBuilder = Callable[..., BaseLiveSTTSession]

_LIVE_STT_BUILDERS: dict[str, LiveSTTBuilder] = {
    "gladia": GladiaLiveSTTSession,
}


def build_live_stt_session(
    provider_id: str,
    *,
    api_key: str | None,
    model: str | None = None,
    language: str = "en",
    endpointing: float = 0.2,
    receive_partials: bool = True,
) -> BaseLiveSTTSession | None:
    """Build a live session when the selected STT supports streaming."""
    builder = _LIVE_STT_BUILDERS.get((provider_id or "").strip().lower())
    if builder is None:
        return None
    return builder(
        api_key=api_key,
        model=model or "solaria-1",
        language=language,
        endpointing=endpointing,
        receive_partials=receive_partials,
    )
