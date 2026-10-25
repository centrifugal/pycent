"""The HTTP handlers: endpoints for client SDKs, JWKS, the proxy, and the ASGI
and WSGI adapters."""

from __future__ import annotations

import asyncio
import io
import json
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

import cent
from cent import endpoints, proxy, token
from cent._http import Handler


def call(h: Handler, method: str = "POST", body: Any = b"", **kw: Any) -> cent.HTTPResponse:
    if not isinstance(body, bytes):
        body = json.dumps(body).encode()
    return h.handle(method, kw.pop("headers", {}), body, **kw)


def as_json(resp: cent.HTTPResponse) -> Any:
    return json.loads(resp.body)


class Errors(list[tuple[cent.HTTPRequest, Exception]]):
    def __call__(self, req: cent.HTTPRequest, err: Exception) -> None:
        self.append((req, err))


# Endpoints for client SDKs.


def test_connection_token() -> None:
    errors = Errors()
    seen: list[cent.HTTPRequest] = []

    def issue(req: cent.HTTPRequest) -> str:
        seen.append(req)
        return "tok"

    h = endpoints.ConnectionToken(issue, on_error=errors)
    for method in ("GET", "POST"):
        resp = call(h, method, headers={"Cookie": "s=1"}, raw="framework request")
        assert resp.status == 200
        assert as_json(resp) == {"token": "tok"}
        assert ("Content-Type", "application/json") in resp.headers
        assert ("Cache-Control", "no-store") in resp.headers
    assert seen[0].headers["cookie"] == "s=1"
    assert seen[0].raw == "framework request"
    resp = call(h, "PUT")
    assert resp.status == 405
    assert ("Allow", "GET, POST") in resp.headers
    assert errors == []


def test_unauthorized_is_403_and_not_an_error() -> None:
    errors = Errors()

    def deny(req: cent.HTTPRequest) -> str:
        raise endpoints.Unauthorized

    def deny_wrapped(req: cent.HTTPRequest) -> str:
        try:
            raise endpoints.Unauthorized("no session")
        except endpoints.Unauthorized as e:
            raise RuntimeError("wrapped") from e

    for f in (deny, deny_wrapped):
        assert call(endpoints.ConnectionToken(f, on_error=errors)).status == 403
    assert errors == []
    # The endpoints' Unauthorized is not the API client's.
    assert not issubclass(endpoints.Unauthorized, cent.UnauthorizedError)


def test_other_errors_are_500_and_reported() -> None:
    errors = Errors()

    def boom(req: cent.HTTPRequest) -> str:
        raise RuntimeError("db down")

    assert call(endpoints.ConnectionToken(boom, on_error=errors)).status == 500
    assert call(endpoints.ConnectionToken(lambda r: "", on_error=errors)).status == 500
    assert [type(e).__name__ for _, e in errors] == ["RuntimeError", "TypeError"]


def test_subscription_token() -> None:
    errors = Errors()
    h = endpoints.SubscriptionToken(lambda r, ch: f"tok:{ch}", on_error=errors)
    assert as_json(call(h, "POST", {"channel": "news"})) == {"token": "tok:news"}
    assert as_json(call(h, "GET", query={"channel": "chat"})) == {"token": "tok:chat"}
    assert call(h, "POST", {}).status == 400
    assert call(h, "GET").status == 400
    assert call(h, "POST", b"{not json").status == 400
    assert call(h, "POST", [1]).status == 400
    assert call(h, "POST", {"channel": 5}).status == 400
    assert call(h, "DELETE").status == 405
    # The five malformed requests, not the wrong method.
    assert len(errors) == 5


def test_shared_poll_signature() -> None:
    errors = Errors()

    def sign(req: cent.HTTPRequest, channel: str, keys: list[str]) -> tuple[list[str], str]:
        return [k for k in keys if k != "secret"], f"sig:{channel}"

    h = endpoints.SharedPollSignature(sign, on_error=errors)
    resp = call(h, "POST", {"channel": "poll:x", "keys": ["a", "secret", "b"]})
    assert as_json(resp) == {"signature": "sig:poll:x", "keys": ["a", "b"]}
    # Keys are always an array.
    resp = call(endpoints.SharedPollSignature(lambda r, c, k: ([], "s")), "POST", {"channel": "poll:x"})
    assert as_json(resp) == {"signature": "s", "keys": []}
    # A key the client did not ask for fails the request.
    bad = endpoints.SharedPollSignature(lambda r, c, k: (["other"], "s"), on_error=errors)
    assert call(bad, "POST", {"channel": "poll:x", "keys": ["a"]}).status == 500
    assert "did not ask for" in str(errors[-1][1])
    assert call(h, "GET").status == 405
    assert call(h, "POST", {"keys": ["a"]}).status == 400


def test_body_limit() -> None:
    errors = Errors()
    h = endpoints.SubscriptionToken(lambda r, ch: "t", on_error=errors)
    assert call(h, "POST", b" " * (1 << 20) + b"{}").status == 400
    assert "over" in str(errors[0][1])


def test_jwks_endpoint() -> None:
    key = token.Key.ed25519(ed25519.Ed25519PrivateKey.generate()).with_key_id("k1")
    h = endpoints.JWKS(key)
    resp = call(h, "GET")
    assert resp.status == 200
    assert as_json(resp)["keys"][0]["kid"] == "k1"
    assert ("Cache-Control", "public, max-age=300") in resp.headers
    head = call(h, "HEAD")
    assert head.status == 200
    assert head.body == b""
    assert call(h, "POST").status == 405
    with pytest.raises(ValueError, match="HMAC"):
        endpoints.JWKS(token.Key.hmac(b"s").with_key_id("h"))


# Sync and async functions.


async def test_async_function() -> None:
    async def issue(req: cent.HTTPRequest) -> str:
        await asyncio.sleep(0)
        return "async-tok"

    h = endpoints.ConnectionToken(issue)
    assert as_json(await h.ahandle("GET")) == {"token": "async-tok"}
    with pytest.raises(TypeError, match="ahandle or asgi"):
        h.handle("GET")
    with pytest.raises(TypeError, match="needs asgi"):
        h.wsgi({"REQUEST_METHOD": "GET"}, lambda *a: None)


async def test_blocking_function_runs_in_a_thread() -> None:
    import threading

    main = threading.get_ident()
    threads: list[int] = []

    def issue(req: cent.HTTPRequest) -> str:
        threads.append(threading.get_ident())
        return "t"

    await endpoints.ConnectionToken(issue).ahandle("GET")
    assert threads[0] != main


# Adapters.


async def asgi_call(h: Handler, method: str, path: str, body: bytes, query: bytes = b"") -> tuple[int, Any, bytes]:
    chunks = [body[: len(body) // 2], body[len(body) // 2 :]]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        part = chunks.pop(0)
        return {"type": "http.request", "body": part, "more_body": bool(chunks)}

    async def send(msg: dict[str, Any]) -> None:
        sent.append(msg)

    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "query_string": query,
        "headers": [(b"content-type", b"application/json"), (b"x-tenant", b"t1")],
    }
    await h.asgi(scope, receive, send)
    start, body_msg = sent
    return start["status"], dict(start["headers"]), body_msg["body"]


async def test_asgi() -> None:
    seen: list[cent.HTTPRequest] = []

    def issue(req: cent.HTTPRequest, channel: str) -> str:
        seen.append(req)
        return f"tok:{channel}"

    status, headers, body = await asgi_call(
        endpoints.SubscriptionToken(issue), "POST", "/centrifugo/sub", b'{"channel":"news"}'
    )
    assert status == 200
    assert headers[b"content-type"] == b"application/json"
    assert json.loads(body) == {"token": "tok:news"}
    assert seen[0].headers["X-Tenant"] == "t1"
    assert seen[0].path == "/centrifugo/sub"
    assert seen[0].raw["type"] == "http"
    status, _, body = await asgi_call(endpoints.SubscriptionToken(issue), "GET", "/", b"", b"channel=a%3Ab")
    assert json.loads(body) == {"token": "tok:a:b"}


async def test_asgi_lifespan() -> None:
    msgs = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return msgs.pop(0)

    async def send(m: dict[str, Any]) -> None:
        sent.append(m)

    await endpoints.ConnectionToken(lambda r: "t").asgi({"type": "lifespan"}, receive, send)
    assert [m["type"] for m in sent] == ["lifespan.startup.complete", "lifespan.shutdown.complete"]


def test_wsgi() -> None:
    started: list[tuple[str, list[tuple[str, str]]]] = []
    body = b'{"channel":"news"}'
    environ = {
        "REQUEST_METHOD": "POST",
        "PATH_INFO": "/centrifugo/sub",
        "QUERY_STRING": "",
        "CONTENT_LENGTH": str(len(body)),
        "CONTENT_TYPE": "application/json",
        "HTTP_X_TENANT": "t1",
        "wsgi.input": io.BytesIO(body),
    }
    seen: list[cent.HTTPRequest] = []

    def issue(req: cent.HTTPRequest, channel: str) -> str:
        seen.append(req)
        return f"tok:{channel}"

    out = endpoints.SubscriptionToken(issue).wsgi(environ, lambda s, h: started.append((s, h)))
    assert started[0][0] == "200 OK"
    assert json.loads(b"".join(out)) == {"token": "tok:news"}
    assert seen[0].headers["x-tenant"] == "t1"
    assert seen[0].raw is environ


def test_wsgi_without_content_length_reads_no_body() -> None:
    class Hang(io.BytesIO):
        def read(self, size: int | None = -1) -> bytes:
            raise AssertionError("read past the request: it would wait on a kept-alive connection")

    started: list[str] = []
    environ = {"REQUEST_METHOD": "GET", "PATH_INFO": "/", "QUERY_STRING": "", "wsgi.input": Hang()}
    out = endpoints.ConnectionToken(lambda r: "t").wsgi(environ, lambda s, h: started.append(s))
    assert started == ["200 OK"]
    assert json.loads(b"".join(out)) == {"token": "t"}


# The proxy.


def test_connect_proxy() -> None:
    seen: list[proxy.ConnectRequest] = []

    def connect(req: cent.HTTPRequest, r: proxy.ConnectRequest) -> proxy.ConnectResult:
        seen.append(r)
        return proxy.ConnectResult(user="42", info={"name": "Alice"}, data=cent.RawJSON('{"n": 1.0}'))

    resp = call(
        proxy.ConnectHandler(connect),
        "POST",
        {"client": "c1", "transport": "websocket", "protocol": "json", "encoding": "json", "data": {"x": [1, 2]}},
    )
    assert resp.status == 200
    assert ("Content-Type", "application/json") in resp.headers
    assert resp.body == b'{"result":{"user":"42","info":{"name":"Alice"},"data":{"n": 1.0}}}'
    assert seen[0].client == "c1"
    assert seen[0].data == {"x": [1, 2]}


def test_empty_result_still_accepts() -> None:
    resp = call(proxy.SubscribeHandler(lambda r, req: proxy.SubscribeResult()), "POST", {"channel": "ch"})
    assert as_json(resp) == {"result": {}}


def test_proxy_answers() -> None:
    errors = Errors()

    def raising(exc: Exception) -> Any:
        def f(req: cent.HTTPRequest, r: Any) -> Any:
            raise exc

        return f

    def wrapped_disconnect(req: cent.HTTPRequest, r: Any) -> Any:
        try:
            raise proxy.Disconnect(4501, "unauthorized")
        except proxy.Disconnect as e:
            raise LookupError("no user") from e

    cases: list[tuple[Any, Any, Any]] = [
        (
            proxy.ConnectHandler(raising(proxy.ProxyError(1000, "nope", temporary=True)), on_error=errors),
            200,
            {"error": {"code": 1000, "message": "nope", "temporary": True}},
        ),
        (
            proxy.ConnectHandler(raising(proxy.Disconnect(4501, "unauthorized"))),
            200,
            {"disconnect": {"code": 4501, "reason": "unauthorized"}},
        ),
        (proxy.ConnectHandler(wrapped_disconnect), 200, {"disconnect": {"code": 4501, "reason": "unauthorized"}}),
        (
            proxy.SharedPollRefreshHandler(raising(proxy.ProxyError(500, "x"))),
            200,
            {"error": {"code": 500, "message": "x"}},
        ),
        # What a proxy type cannot carry fails the request.
        (proxy.SharedPollRefreshHandler(raising(proxy.Disconnect(4000, "x")), on_error=errors), 500, None),
        (proxy.RefreshHandler(raising(proxy.ProxyError(400, "x")), on_error=errors), 500, None),
        (proxy.RefreshHandler(raising(proxy.Disconnect(4000, "x")), on_error=errors), 500, None),
        (proxy.PublishHandler(raising(RuntimeError("db down")), on_error=errors), 500, None),
    ]
    for h, status, body in cases:
        resp = call(h, "POST", {"channel": "ch"})
        assert resp.status == status, h
        if body is not None:
            assert as_json(resp) == body
    assert len(errors) == 4
    assert "cannot answer" in str(errors[0][1])


def test_proxy_refusals() -> None:
    errors = Errors()
    ok = proxy.PublishHandler(lambda r, req: proxy.PublishResult(), on_error=errors)
    assert call(ok, "GET").status == 405
    assert call(ok, "POST", b"{").status == 400
    assert call(ok, "POST", {"channel": 5}).status == 400
    wrong = proxy.PublishHandler(lambda r, req: proxy.ConnectResult(), on_error=errors)  # type: ignore[arg-type, return-value]
    assert call(wrong, "POST", {}).status == 500
    nan = proxy.PublishHandler(lambda r, req: proxy.PublishResult(data=float("nan")), on_error=errors)
    assert call(nan, "POST", {}).status == 500
    small = proxy.PublishHandler(lambda r, req: proxy.PublishResult(), max_body=10, on_error=errors)
    assert call(small, "POST", {"channel": "long channel name"}).status == 400
    assert len(errors) == 5
    with pytest.raises(ValueError, match="max_body"):
        proxy.PublishHandler(lambda r, req: proxy.PublishResult(), max_body=0)


def test_proxy_payload_round_trip() -> None:
    """The publish proxy answering with the client's data changes nothing."""
    original = '{"a":{},"b":{"0":"a"},"c":18446744073709551617,"d":1.0}'
    h = proxy.PublishHandler(lambda r, req: proxy.PublishResult(data=req.data))
    resp = h.handle("POST", {}, ('{"channel":"ch","data":' + original + "}").encode())
    assert resp.body == b'{"result":{"data":' + original.encode() + b"}}"


def test_proxy_binary_mode() -> None:
    def publish(req: cent.HTTPRequest, r: proxy.PublishRequest) -> proxy.PublishResult:
        assert r.encoding == "binary"
        return proxy.PublishResult(b64data=r.b64data)

    resp = call(proxy.PublishHandler(publish), "POST", {"channel": "ch", "b64data": "AQI=", "encoding": "binary"})
    assert as_json(resp) == {"result": {"b64data": "AQI="}}


def test_refresh_expired() -> None:
    h = proxy.RefreshHandler(lambda r, req: proxy.RefreshResult(expired=True))
    assert as_json(call(h, "POST", {"client": "c", "user": "u"})) == {"result": {"expired": True}}


async def test_async_proxy_function() -> None:
    async def subscribe(req: cent.HTTPRequest, r: proxy.SubscribeRequest) -> proxy.SubscribeResult:
        if r.channel == "secret":
            raise proxy.ProxyError(403, "permission denied")
        return proxy.SubscribeResult(info={"ok": True})

    h = proxy.SubscribeHandler(subscribe)
    assert json.loads((await h.ahandle("POST", {}, b'{"channel":"news"}')).body) == {"result": {"info": {"ok": True}}}
    assert json.loads((await h.ahandle("POST", {}, b'{"channel":"secret"}')).body) == {
        "error": {"code": 403, "message": "permission denied"}
    }


def test_every_proxy_type_has_a_handler() -> None:
    names = [n for n in proxy.__all__ if n.endswith("Handler")]
    assert len(names) == 11
