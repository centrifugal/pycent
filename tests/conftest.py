"""A fake Centrifugo for the unit tests, behind httpx's MockTransport."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

import cent

ENDPOINT = "http://centrifugo.test/api"

Handler = Callable[[str, dict[str, Any]], Any]


@dataclass
class Fake:
    """Answers each API method with what its handler returns: a result dict
    (wrapped as {"result": ...}), an httpx.Response, or a cent.ApiError (as
    {"error": ...}). Batches are answered command by command."""

    handlers: dict[str, Handler] = field(default_factory=dict)
    requests: list[httpx.Request] = field(default_factory=list)

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

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        method = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content)
        if method == "batch" and "batch" not in self.handlers:
            replies = []
            for cmd in body["commands"]:
                ((m, b),) = cmd.items()
                replies.append(_reply(m, self._answer(m, b)))
            return httpx.Response(200, json={"replies": replies})
        out = self._answer(method, body)
        if isinstance(out, httpx.Response):
            return out
        return httpx.Response(200, json=_envelope(out))


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
    http = httpx.Client(transport=httpx.MockTransport(fake))
    return cent.Client(ENDPOINT, api_key="key", http_client=http)


@pytest.fixture
def aclient(fake: Fake) -> cent.AsyncClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    return cent.AsyncClient(ENDPOINT, api_key="key", http_client=http)
