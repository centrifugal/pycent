"""A fake Centrifugo for the unit tests, behind httpx2's MockTransport."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx2
import pytest

import cent

ENDPOINT = "http://centrifugo.test/api"

Handler = Callable[[str, dict[str, Any]], Any]


@dataclass
class Fake:
    """Answers each API method with what its handler returns: a result dict
    (wrapped as {"result": ...}), an httpx2.Response, or a cent.ApiError (as
    {"error": ...}). Batches are answered command by command."""

    handlers: dict[str, Handler] = field(default_factory=dict)
    requests: list[httpx2.Request] = field(default_factory=list)

    def on(self, method: str, handler: Handler | Any) -> None:
        self.handlers[method] = handler if callable(handler) else (lambda _m, _b: handler)

    def bodies(self, method: str | None = None) -> list[dict[str, Any]]:
        out = []
        for r in self.requests:
            if method is None or r.url.path.endswith("/" + method):
                out.append(json.loads(r.content))
        return out

    def _answer(self, method: str, body: dict[str, Any]) -> Any:
        h = self.handlers.get(method)
        if h is None:
            return default_result(method, body)
        return h(method, body)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        method = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content)
        if method == "batch" and "batch" not in self.handlers:
            replies = []
            for cmd in body["commands"]:
                ((m, b),) = cmd.items()
                replies.append(_reply(m, self._answer(m, b)))
            return httpx2.Response(200, json={"replies": replies})
        out = self._answer(method, body)
        if isinstance(out, httpx2.Response):
            return out
        return httpx2.Response(200, json=_envelope(out))


def _envelope(out: Any) -> dict[str, Any]:
    if isinstance(out, cent.ApiError):
        e: dict[str, Any] = {"code": out.code, "message": out.message}
        if out.temporary:
            e["temporary"] = True
        return {"error": e}
    return {"result": out}


def _reply(method: str, out: Any) -> dict[str, Any]:
    env = _envelope(out)
    if "error" in env:
        return env
    return {method: env["result"]}


def default_result(method: str, body: dict[str, Any]) -> Any:
    """A plausible success for each method."""
    if method == "publish":
        return {"offset": 1, "epoch": "e1"}
    if method == "broadcast":
        out = []
        for ch in body["channels"]:
            if ch.startswith("bad:"):
                out.append({"error": {"code": 102, "message": "unknown channel"}})
            elif ch.startswith("full:"):
                out.append({"error": {"code": 108, "message": "not available"}})
            elif ch.startswith("flaky:"):
                out.append({"error": {"code": 100, "message": "internal server error", "temporary": True}})
            else:
                out.append({"result": {"offset": 1, "epoch": "e1"}})
        return {"responses": out}
    return {}


@pytest.fixture
def fake() -> Fake:
    return Fake()


@pytest.fixture
def client(fake: Fake) -> cent.Client:
    http = httpx2.Client(transport=httpx2.MockTransport(fake))
    return cent.Client(ENDPOINT, api_key="key", http_client=http)


@pytest.fixture
def aclient(fake: Fake) -> cent.AsyncClient:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(fake))
    return cent.AsyncClient(ENDPOINT, api_key="key", http_client=http)


class Api:
    """Runs a client's calls the same way for Client and AsyncClient."""

    def __init__(self, kind: str, fake: Fake, **opts: Any) -> None:
        self.kind = kind
        self.fake = fake
        self.loop = asyncio.new_event_loop() if kind == "async" else None
        if kind == "async":
            http_a = opts.pop("http_client", None) or httpx2.AsyncClient(transport=httpx2.MockTransport(fake))
            opts.setdefault("api_endpoint", ENDPOINT)
            self.client: Any = cent.AsyncClient(http_client=http_a, **opts)
        else:
            http_s = opts.pop("http_client", None) or httpx2.Client(transport=httpx2.MockTransport(fake))
            opts.setdefault("api_endpoint", ENDPOINT)
            self.client = cent.Client(http_client=http_s, **opts)

    def run(self, v: Any) -> Any:
        if self.loop is not None:
            return self.loop.run_until_complete(v)
        return v

    def __getattr__(self, name: str) -> Callable[..., Any]:
        method = getattr(self.client, name)
        return lambda *a, **kw: self.run(method(*a, **kw))

    def send(self, batch: Any, **kw: Any) -> Any:
        return self.run(batch.send(**kw))

    def close(self, timeout: float | None = None) -> None:
        if self.kind == "async":
            self.run(self.client.aclose(timeout))
        else:
            self.client.close(timeout)


@pytest.fixture(params=["sync", "async"])
def kind(request: pytest.FixtureRequest) -> str:
    return str(request.param)


@pytest.fixture
def new_api(kind: str, fake: Fake) -> Iterator[Callable[..., Api]]:
    """Makes Apis of the test's kind, and closes their event loops."""
    made: list[Api] = []

    def make(**opts: Any) -> Api:
        a = Api(kind, fake, **opts)
        made.append(a)
        return a

    yield make
    for a in made:
        if a.loop is not None:
            a.loop.close()


@pytest.fixture
def api(new_api: Callable[..., Api]) -> Api:
    return new_api(api_key="key")
