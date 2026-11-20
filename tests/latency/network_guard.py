"""Socket-level outbound network denial for offline latency tests."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch


class OutboundNetworkError(RuntimeError):
    """Raised when an offline test attempts a non-loopback connection."""


def _is_loopback(host: object) -> bool:
    if isinstance(host, bytes):
        host = host.decode("ascii", errors="ignore")
    if not isinstance(host, str):
        return False
    normalized = host.strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


@contextmanager
def deny_outbound_network() -> Iterator[list[str]]:
    attempts: list[str] = []
    original_getaddrinfo = socket.getaddrinfo
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_create_connection = socket.create_connection

    def reject(host: object) -> None:
        if _is_loopback(host):
            return
        rendered = str(host)
        attempts.append(rendered)
        raise OutboundNetworkError(f"offline test blocked outbound network: {rendered}")

    def guarded_getaddrinfo(host: object, *args: Any, **kwargs: Any):
        reject(host)
        return original_getaddrinfo(host, *args, **kwargs)

    def guarded_connect(sock: socket.socket, address: object):
        host = address[0] if isinstance(address, tuple) and address else address
        reject(host)
        return original_connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: object):
        host = address[0] if isinstance(address, tuple) and address else address
        reject(host)
        return original_connect_ex(sock, address)

    def guarded_create_connection(address: object, *args: Any, **kwargs: Any):
        host = address[0] if isinstance(address, tuple) and address else address
        reject(host)
        return original_create_connection(address, *args, **kwargs)

    with (
        patch("socket.getaddrinfo", guarded_getaddrinfo),
        patch.object(socket.socket, "connect", guarded_connect),
        patch.object(socket.socket, "connect_ex", guarded_connect_ex),
        patch("socket.create_connection", guarded_create_connection),
    ):
        yield attempts
