"""Anti-pattern guards for foundation hardening (H6)."""

from __future__ import annotations

import pytest

from core.runtime.env import BootConfigurationError, require_production_secrets
from core.secrets.kms.local_dev import LocalDevKMSBackend


def test_no_local_dev_kms_default_in_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.delenv("UCVE_MASTER_KEY", raising=False)
    with pytest.raises(RuntimeError):
        LocalDevKMSBackend()


def test_prod_boot_refuses_default_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_ENV", "production")
    monkeypatch.setenv("UCVE_JWT_SECRET", "change-me")
    monkeypatch.setenv("UCVE_MINT_HMAC_SECRET", "ok-mint-secret-value-32chars!!")
    monkeypatch.setenv("UCVE_METRICS_BEARER", "ok-metrics-bearer-value-32ch")
    with pytest.raises(BootConfigurationError):
        require_production_secrets()


def test_null_providers_disallowed_flag() -> None:
    from worker_raw.orchestration.pipeline import build_providers

    stt, llm, tts = build_providers(allow_null=False)
    assert stt.__class__.__name__ != "NullSTTProvider"
    assert llm.__class__.__name__ != "NullLLMProvider"
    assert tts.__class__.__name__ != "NullTTSProvider"
