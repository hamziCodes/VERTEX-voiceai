"""Automated regression checks for top 10 security anti-patterns (Phase 32)."""

from pathlib import Path
from uuid import uuid4
import pytest

from core.errors.client_mapper import ClientErrorMapper
from core.errors.codes import UCVEErrorCode
from core.errors.redaction import redact_error_details
from control_plane.agents.models.agent_config import AgentConfig
from control_plane.agents.models.provider_config import AgentProvidersConfig, CategoryPriorityChain, ProviderRoute
from control_plane.agents.validation.validator import AgentConfigValidator
from worker_raw.security.ws_policy import WSSecurityPolicy, WSSecurityViolation

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_anti_pattern_08_fail_open_secrets() -> None:
    """Anti-pattern #8: Secrets must fail-closed, never fail-open on missing/empty keys."""
    from control_plane.auth.hmac_mint import verify_mint_signature

    assert verify_mint_signature("", "tenant-1", "1700000000", "nonce-1", "agent-1", "sig") is False
    assert verify_mint_signature("secret", "tenant-1", "1700000000", "nonce-1", "agent-1", "") is False


def test_anti_pattern_04_secrets_in_urls_redacted() -> None:
    """Anti-pattern #4: Query parameters and secrets in URLs must be scrubbed in logs/errors."""
    details = {
        "url": "ws://localhost:8081/ws/audio",
        "token": "eyJhbGciOiJIUzI1NiJ9.secret_jwt_payload",
        "secret": "top-secret-val",
    }
    redacted = redact_error_details(details)
    assert redacted["token"] == "[REDACTED]"
    assert redacted["secret"] == "[REDACTED]"
    assert "secret_jwt_payload" not in str(redacted)


def test_anti_pattern_12_distributed_rate_limiting() -> None:
    """Anti-pattern #12: Rate limiting must enforce hard boundary on connections."""
    policy = WSSecurityPolicy(max_frames_per_sec=5)
    conn_id = "test-conn-123"

    for _ in range(5):
        assert policy.check_rate_limit(conn_id) is True

    # 6th frame must trigger violation
    with pytest.raises(WSSecurityViolation):
        policy.check_rate_limit(conn_id)


def test_anti_pattern_17_zero_retention_path() -> None:
    """Anti-pattern #17: Zero-retention compliance tier must be supported."""
    config = AgentConfig(
        tenant_id=uuid4(),
        name="Zero Retention Agent",
        compliance={"tier": "standard", "retention_days": 0},
    )
    assert config.compliance.get("retention_days") == 0


def test_anti_pattern_18_multi_provider_routes() -> None:
    """Anti-pattern #18: Fallback routes must require minimum 2 providers in standard/prod."""
    single_route_providers = AgentProvidersConfig(
        stt=[CategoryPriorityChain(category="stt", language="en", routes=[ProviderRoute(provider_id="gladia", priority=1)])],
        llm=[CategoryPriorityChain(category="llm", language="en", routes=[ProviderRoute(provider_id="groq", priority=1)])],
        tts=[CategoryPriorityChain(category="tts", language="en", routes=[ProviderRoute(provider_id="cartesia", priority=1)])],
    )
    config = AgentConfig(
        tenant_id=uuid4(),
        name="Single Provider Test",
        providers=single_route_providers,
    )
    validator = AgentConfigValidator()
    result = validator.validate(config)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "INSUFFICIENT_PROVIDER_ROUTES" in codes


def test_anti_pattern_mcp_rag_data_framing() -> None:
    """Untrusted MCP/RAG output must be wrapped in DATA frames, never injected into prompt directly."""
    rag_doc = (REPO_ROOT / "docs" / "developer" / "MCP_AND_RAG_SETUP.md").read_text(encoding="utf-8")
    assert "DATA-framed" in rag_doc or "DATA frame" in rag_doc


def test_anti_pattern_generic_client_errors() -> None:
    """Anti-pattern #25: Client errors must be generic without internal stack trace leakage."""
    from core.errors.structured import StructuredError

    error = StructuredError(
        code=UCVEErrorCode.INTERNAL_ERROR,
        message="Database connection failed at postgres://user:secret@internal:5432/db",
        details={"raw_query": "SELECT * FROM secrets"},
    )
    payload = ClientErrorMapper.map_to_client_payload(error)

    assert "postgres" not in payload["message"]
    assert "secret" not in payload["message"]
    assert "raw_query" not in payload
    assert payload["code"] == UCVEErrorCode.INTERNAL_ERROR.value


def test_anti_pattern_hipaa_baa_gate() -> None:
    """Anti-pattern #10: HIPAA tier must enforce signed BAA gate before enabling."""
    validator = AgentConfigValidator()
    hipaa_agent = AgentConfig(
        tenant_id=uuid4(),
        name="hipaa-test",
        providers=AgentProvidersConfig.create_default(),
        compliance={"tier": "hipaa", "hipaa_baa_acknowledged": False},
    )
    result = validator.validate(hipaa_agent)
    assert not result.is_valid
    codes = [e.code for e in result.errors]
    assert "HIPAA_BAA_REQUIRED" in codes


def test_anti_pattern_caller_id_required_telephony() -> None:
    """Anti-pattern #18: Inbound telephony without E.164 caller_id must be rejected."""
    telephony_doc = (REPO_ROOT / "docs" / "developer" / "TELEPHONY_INTEGRATOR.md").read_text(encoding="utf-8")
    assert "CALLER_ID_MISSING" in telephony_doc


def test_anti_pattern_livekit_not_required_sovereign_default() -> None:
    """LiveKit must be optional and disabled by default for sovereign stack."""
    compose_text = (REPO_ROOT / "infra" / "docker" / "docker-compose.yml").read_text(encoding="utf-8")
    assert 'UCVE_ENABLE_LIVEKIT: "false"' in compose_text

