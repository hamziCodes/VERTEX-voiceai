"""Stage 3: the KMS backend is chosen explicitly and fails closed."""

from __future__ import annotations

import sys
import types

import pytest

from core.secrets.kms.local_dev import LocalDevKMSBackend
from core.secrets.kms.select import KMSConfigurationError, kms_backend_from_environment
from core.secrets.vault import SecretVault


def test_default_is_local(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("UCVE_KMS_BACKEND", raising=False)
    monkeypatch.setenv("AWS_KMS_KEY_ID", "alias/should-not-switch-implicitly")
    assert isinstance(kms_backend_from_environment(), LocalDevKMSBackend)


def test_unknown_backend_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_KMS_BACKEND", "gcp")
    with pytest.raises(KMSConfigurationError):
        kms_backend_from_environment()


def test_aws_requires_a_key_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("UCVE_KMS_BACKEND", "aws")
    monkeypatch.delenv("AWS_KMS_KEY_ID", raising=False)
    with pytest.raises(KMSConfigurationError):
        kms_backend_from_environment()


def test_vault_round_trips_through_aws_kms(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class _FakeKms:
        def encrypt(self, KeyId: str, Plaintext: bytes) -> dict[str, bytes]:  # noqa: N803
            calls.append(f"encrypt:{KeyId}")
            return {"CiphertextBlob": b"wrapped:" + Plaintext[::-1]}

        def decrypt(self, CiphertextBlob: bytes) -> dict[str, bytes]:  # noqa: N803
            calls.append("decrypt")
            return {"Plaintext": CiphertextBlob.removeprefix(b"wrapped:")[::-1]}

    fake_boto3 = types.SimpleNamespace(client=lambda service, region_name: _FakeKms())
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)
    monkeypatch.setenv("UCVE_KMS_BACKEND", "aws")
    monkeypatch.setenv("AWS_KMS_KEY_ID", "alias/wavia-test")

    vault = SecretVault()
    blob, version = vault.envelope.encrypt_secret("sk-test-value")
    assert "sk-test-value" not in blob
    assert vault.envelope.decrypt_secret(blob, version) == "sk-test-value"
    assert calls == ["encrypt:alias/wavia-test", "decrypt"]
