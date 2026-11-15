"""Load-test bootstrap: the real worker app plus a seeded in-memory tenant.

Test-only. It runs ``worker_raw.main:app`` unchanged in this process and adds
one route, ``POST /__loadtest/mint``, that mints sessions through the real
control-plane mint path against the same in-memory repositories the worker
reads. Nothing here ships in a product image (tests/ is excluded).

Usage: ``python -m tests.scaling.worker_bootstrap --port 18081``
Environment must select mock providers (``RUN_MOCK_PROVIDERS=1``).
"""

from __future__ import annotations

import argparse
import asyncio
import faulthandler
import os
import sys
import time
from uuid import UUID, uuid4

import uvicorn

from control_plane.agents.repo import AgentConfigRepo
from control_plane.auth.hmac_mint import expected_signature
from control_plane.routes.session import get_default_mint_context, handle_session_mint
from core.db.models import Agent, Tenant
from core.secrets.vault import SecretVault
from tests.agents.test_session_plan_compiler import make_config, publish
from worker_raw.main import app

_SECRET = "load-test-mint-secret"
_VAULT = SecretVault()


_REPO = AgentConfigRepo()
_TENANTS: dict[int, tuple[str, str]] = {}


async def _seed(index: int) -> tuple[str, str]:
    ctx = get_default_mint_context()
    tenant_id, agent_id = str(uuid4()), str(uuid4())
    publish(_REPO, make_config(UUID(tenant_id), UUID(agent_id)))
    ctx.agent_config_repo = _REPO
    await ctx.tenant_repo.create_tenant(Tenant(id=tenant_id, name="Load test"))
    await ctx.tenant_repo.save_agent(
        Agent(id=agent_id, tenant_id=tenant_id, name="Load")
    )
    # Placeholder BYOK records so the published chains bind. The values are
    # not keys; RUN_MOCK_PROVIDERS=1 means no adapter sends them anywhere.
    # In-memory mode builds a fresh vault per session, so the harness shares one
    # seeded vault with the worker's provider binder (test-only patch).
    import worker_raw.orchestration.provider_binding as binding

    binding.build_secret_vault = lambda **_kwargs: _VAULT  # type: ignore[assignment]
    vault = _VAULT
    for provider, ref in (
        ("gladia", "cred/stt-primary"),
        ("deepgram", "cred/stt-secondary"),
        ("groq", "cred/llm-primary"),
        ("gemini", "cred/llm-secondary"),
        ("cartesia", "cred/tts-primary"),
        ("uplift", "cred/tts-secondary"),
    ):
        await vault.astore(
            tenant_id, provider, "load-test-placeholder-not-a-key", credential_ref=ref
        )
    _TENANTS[index] = (tenant_id, agent_id)
    return tenant_id, agent_id


@app.get("/__loadtest/pid", include_in_schema=False)
async def _loadtest_pid() -> dict[str, int]:
    """The interpreter's own PID (a venv launcher may sit in front of it)."""
    return {"pid": os.getpid()}


@app.post("/__loadtest/mint", include_in_schema=False)
async def _loadtest_mint(tenant: int = 0) -> dict[str, object]:
    """Mint for synthetic tenant ``tenant`` (each tenant has its own quota)."""
    tenant_id, agent_id = _TENANTS.get(tenant) or await _seed(tenant)
    timestamp = str(int(time.time()))
    nonce = uuid4().hex
    signature = expected_signature(_SECRET, tenant_id, timestamp, nonce, agent_id)
    status, body = await handle_session_mint(
        tenant_id,
        timestamp,
        nonce,
        agent_id,
        signature,
        secret=_SECRET,
        ctx=get_default_mint_context(),
    )
    return {"status": status, **body}


def _install_slow_callback_probe(threshold_s: float) -> None:
    """Log any event-loop callback that blocks longer than ``threshold_s``."""
    import asyncio.events
    import traceback

    original = asyncio.events.Handle._run

    def timed(self: asyncio.events.Handle) -> None:
        started = time.perf_counter()
        original(self)
        elapsed = time.perf_counter() - started
        if elapsed >= threshold_s:
            callback = getattr(self, "_callback", None)
            target = getattr(callback, "__self__", None)
            coro = getattr(target, "get_coro", lambda: None)()
            where = ""
            if coro is not None and getattr(coro, "cr_frame", None) is not None:
                where = "".join(traceback.format_stack(coro.cr_frame, limit=6))
            sys.stderr.write(
                f"SLOW_CALLBACK {elapsed * 1000:.0f}ms {callback!r}\n{where}\n"
            )

    asyncio.events.Handle._run = timed  # type: ignore[method-assign]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()
    dump_after = float(os.environ.get("LOADTEST_STACKDUMP_S", "0") or 0)
    if dump_after > 0:
        target = os.environ.get("LOADTEST_STACKDUMP_FILE")
        stream = open(target, "w", encoding="utf-8") if target else sys.stderr  # noqa: SIM115
        faulthandler.dump_traceback_later(dump_after, repeat=True, file=stream)
    slow_ms = float(os.environ.get("LOADTEST_SLOW_CALLBACK_MS", "0") or 0)
    if slow_ms > 0:
        _install_slow_callback_probe(slow_ms / 1000.0)
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
    uvicorn.run(
        app, host="127.0.0.1", port=args.port, log_level="warning", ws_max_size=2**20
    )


if __name__ == "__main__":
    main()
