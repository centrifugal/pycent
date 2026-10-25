"""The integration tests run against a real Centrifugo, set up as
testdata/centrifugo.json says - history and presence for channels without a
namespace, a "map" and a "poll" namespace, HMAC and Ed25519 client tokens, the
unidirectional HTTP stream, the connect and refresh proxies:

    docker compose -f testdata/centrifugo-pro.compose.yml up -d --wait   # Centrifugo PRO
    make test-integration

PYCENT_TEST_ADDR and PYCENT_TEST_API_KEY default to http://localhost:8100/api
and "api_key". The PRO tests skip against Centrifugo OSS, unless PYCENT_TEST_PRO
is set: then a server which is not PRO fails them.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

import httpx
import pytest

import cent

ADDR = os.environ.get("PYCENT_TEST_ADDR", "http://localhost:8100/api")
API_KEY = os.environ.get("PYCENT_TEST_API_KEY", "api_key")


@pytest.fixture
def client() -> Iterator[cent.Client]:
    c = cent.Client(ADDR, api_key=API_KEY)
    try:
        c.info()
    except cent.CentError as e:
        pytest.fail(f"Centrifugo not reachable at {ADDR}: {e}")
    yield c
    c.close()


@pytest.fixture
def pro(client: cent.Client) -> cent.Client:
    try:
        client.connections(cent.ConnectionsRequest(user="nobody"))
    except cent.CentError as e:
        if os.environ.get("PYCENT_TEST_PRO"):
            pytest.fail(f"PYCENT_TEST_PRO is set, but the server is not Centrifugo PRO: {e}")
        pytest.skip(f"not Centrifugo PRO: {e}")
    return client


@pytest.fixture
def unique(request: pytest.FixtureRequest) -> Callable[[str], str]:
    def make(prefix: str = "") -> str:
        return f"{prefix}pycent-{request.node.name}-{time.time_ns():x}".replace("[", "-").replace("]", "")

    return make


class _Quiet(WSGIRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


class _Threaded(WSGIServer):
    """wsgiref's server, a thread per request: Centrifugo calls proxies concurrently."""

    daemon_threads = True

    def process_request(self, request: Any, client_address: Any) -> None:
        t = threading.Thread(target=self._handle, args=(request, client_address), daemon=True)
        t.start()

    def _handle(self, request: Any, client_address: Any) -> None:
        try:
            self.finish_request(request, client_address)
        finally:
            self.shutdown_request(request)


@pytest.fixture
def serve() -> Iterator[Callable[[int, Any], None]]:
    """Serves a WSGI app on all interfaces at port, where Centrifugo reaches it
    as host.docker.internal from its container."""
    servers: list[WSGIServer] = []

    def start(port: int, app: Any) -> None:
        srv = make_server("0.0.0.0", port, app, server_class=_Threaded, handler_class=_Quiet)  # noqa: S104
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)

    yield start
    for srv in servers:
        srv.shutdown()
        srv.server_close()


class Stream:
    """A client connection over Centrifugo's unidirectional HTTP stream."""

    def __init__(self, body: dict[str, Any]) -> None:
        self._http = httpx.Client(timeout=30)
        self._cm = self._http.stream("POST", ADDR.removesuffix("/api") + "/connection/uni_http_stream", json=body)
        self._resp = self._cm.__enter__()
        self._lines = self._resp.iter_lines()

    def next(self) -> dict[str, Any] | None:
        """The next message, None once the connection is closed; pings skipped."""
        for line in self._lines:
            if not line or line == "{}":
                continue
            msg: dict[str, Any] = json.loads(line)
            return msg
        return None

    def close(self) -> None:
        self._cm.__exit__(None, None, None)
        self._http.close()


@pytest.fixture
def stream() -> Iterator[Callable[[dict[str, Any]], Stream]]:
    opened: list[Stream] = []

    def open_(body: dict[str, Any]) -> Stream:
        s = Stream(body)
        opened.append(s)
        return s

    yield open_
    for s in opened:
        s.close()
