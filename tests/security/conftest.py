"""Fixtures for security tests (Phase 32)."""

from __future__ import annotations

import pytest


@pytest.fixture
def mock_secret_key() -> str:
    return "test-secret-key-32-chars-long-minimum-needed"
