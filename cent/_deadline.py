"""One deadline for a whole request of the blocking client.

httpx2 bounds each phase of a request on its own - a connect, a write, every
socket read - so a reply arriving in pieces, headers included, can outlast any
timeout given per phase. The default HTTP client of a Client sends through
_DeadlineBackend instead: an httpcore2 network backend which bounds every
connect, read and write by the time left until the call's deadline, set in a
context variable around the request. The async client needs none of this:
asyncio.timeout bounds its whole call.
"""

from __future__ import annotations

import time
import typing
import urllib.request
from contextvars import ContextVar
from typing import Any

import httpcore2
import httpx2

# The monotonic deadline of the request the current thread sends, if any.
deadline: ContextVar[float | None] = ContextVar("cent_deadline", default=None)


def _left(timeout: float | None, exc: type[Exception]) -> float | None:
    d = deadline.get()
    if d is None:
        return timeout
    left = d - time.monotonic()
    if left <= 0:
        raise exc("cent: the call's deadline passed")
    return left if timeout is None else min(timeout, left)


class _Stream(httpcore2.NetworkStream):
    def __init__(self, inner: httpcore2.NetworkStream) -> None:
        self._inner = inner

    def read(self, max_bytes: int, timeout: float | None = None) -> bytes:
        return self._inner.read(max_bytes, _left(timeout, httpcore2.ReadTimeout))

    def write(self, buffer: bytes, timeout: float | None = None) -> None:
        self._inner.write(buffer, _left(timeout, httpcore2.WriteTimeout))

    def close(self) -> None:
        self._inner.close()

    def start_tls(
        self, ssl_context: Any, server_hostname: str | None = None, timeout: float | None = None
    ) -> httpcore2.NetworkStream:
        return _Stream(self._inner.start_tls(ssl_context, server_hostname, _left(timeout, httpcore2.ConnectTimeout)))

    def get_extra_info(self, info: str) -> Any:
        return self._inner.get_extra_info(info)


class _DeadlineBackend(httpcore2.NetworkBackend):
    def __init__(self) -> None:
        self._inner = httpcore2.SyncBackend()

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[Any] | None = None,
    ) -> httpcore2.NetworkStream:
        t = _left(timeout, httpcore2.ConnectTimeout)
        return _Stream(self._inner.connect_tcp(host, port, t, local_address, socket_options))

    def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: typing.Iterable[Any] | None = None
    ) -> httpcore2.NetworkStream:
        t = _left(timeout, httpcore2.ConnectTimeout)
        return _Stream(self._inner.connect_unix_socket(path, t, socket_options))

    def sleep(self, seconds: float) -> None:
        self._inner.sleep(seconds)


def _env_proxies() -> bool:
    proxies = urllib.request.getproxies()
    return any(k in proxies for k in ("http", "https", "all"))


def http_client(limits: httpx2.Limits) -> httpx2.Client:
    """The default HTTP client of a Client: its requests bounded by one deadline
    each. With a proxy configured in the environment, httpx2 builds the
    transports for it, and the deadline is enforced between the phases of a
    request and the chunks of its body only."""
    if _env_proxies():
        return httpx2.Client(limits=limits, follow_redirects=False, timeout=None)
    transport = httpx2.HTTPTransport(limits=limits)
    # httpx2 builds its connection pool with the default network backend, and
    # has no option for another: the pool is replaced by one with ours.
    # tests/test_client.py's test_deadline_bounds_a_trickling_reply fails if
    # httpx2 changes this.
    transport._pool = httpcore2.ConnectionPool(
        ssl_context=httpx2.create_ssl_context(),
        max_connections=limits.max_connections,
        max_keepalive_connections=limits.max_keepalive_connections,
        keepalive_expiry=limits.keepalive_expiry,
        network_backend=_DeadlineBackend(),
    )
    return httpx2.Client(transport=transport, follow_redirects=False, timeout=None)
