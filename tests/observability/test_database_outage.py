"""Phase 15 network drill: a lost database fails fast and cleanly."""

from __future__ import annotations

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from core.db.async_pg import connection_kwargs, pool_wait_timeout_s
from core.db.http_errors import DATABASE_UNAVAILABLE, install_database_error_handlers


@pytest.mark.parametrize(
    "error",
    [PoolTimeout("couldn't get a connection after 5.00 sec"), psycopg.OperationalError("lost")],
)
def test_database_outage_is_a_json_503_with_retry_after(error: Exception) -> None:
    app = FastAPI()
    install_database_error_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise error

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/boom")

    assert response.status_code == 503
    assert response.json() == DATABASE_UNAVAILABLE
    assert response.headers["retry-after"] == "5"
    assert "lost" not in response.text and "sec" not in response.text


@pytest.mark.parametrize(
    "module",
    ["control_plane.app", "worker_raw.main", "worker_jobs.main", "telephony_gateway.main"],
)
def test_every_service_installs_the_database_outage_handler(module: str) -> None:
    import importlib

    app = importlib.import_module(module).app
    assert PoolTimeout in app.exception_handlers
    assert psycopg.OperationalError in app.exception_handlers


def test_pool_and_connections_have_bounded_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("UCVE_DB_POOL_TIMEOUT_S", "UCVE_DB_CONNECT_TIMEOUT_S", "UCVE_DB_TCP_USER_TIMEOUT_S"):
        monkeypatch.delenv(name, raising=False)
    assert pool_wait_timeout_s() == 5.0
    kwargs = connection_kwargs()
    assert kwargs["connect_timeout"] == 3
    assert kwargs["tcp_user_timeout"] == 5000
    assert kwargs["keepalives"] == 1

    monkeypatch.setenv("UCVE_DB_POOL_TIMEOUT_S", "2.5")
    monkeypatch.setenv("UCVE_DB_CONNECT_TIMEOUT_S", "not-a-number")
    assert pool_wait_timeout_s() == 2.5
    assert connection_kwargs()["connect_timeout"] == 3


def test_pool_checks_connections_before_handing_them_out() -> None:
    import inspect

    from core.db import async_pg

    source = inspect.getsource(async_pg.AsyncDatabase.open)
    assert "check=AsyncConnectionPool.check_connection" in source
