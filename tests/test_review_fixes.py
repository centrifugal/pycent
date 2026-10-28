"""Regressions found in review: the blocking client's deadline, contexts of
automatic batches, header encoding, decoding errors, deep JSON."""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import gzip
import json
import socket
import threading
import time
from collections.abc import Iterator
from typing import Any

import httpx2
import pytest

import cent
from cent import endpoints, proxy
from tests.conftest import ENDPOINT, Fake


@pytest.fixture
def trickling_server(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """A server sending its reply's headers one line every 0.1 s."""
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    stop = threading.Event()

    def serve() -> None:
        while not stop.is_set():
            try:
                c, _ = srv.accept()
            except OSError:
                return
            with c:
                c.recv(65536)
                try:
                    c.sendall(b"HTTP/1.1 200 OK\r\n")
                    for _ in range(40):
                        c.sendall(b"X-A: b\r\n")
                        time.sleep(0.1)
                    c.sendall(b"Content-Length: 2\r\n\r\n{}")
                except OSError:
                    pass

    threading.Thread(target=serve, daemon=True).start()
    yield srv.getsockname()[1]
    stop.set()
    srv.close()


def test_deadline_bounds_a_trickling_reply(trickling_server: int) -> None:
    """The default HTTP client bounds a request by one deadline, headers
    included: httpx2's own timeouts bound each socket read only. This also
    fails if httpx2 changes how the default client's pool is replaced."""
    c = cent.Client(f"http://127.0.0.1:{trickling_server}/api", api_key="k")
    start = time.monotonic()
    with pytest.raises(cent.CentTimeoutError):
        c.info(timeout=0.5)
    assert time.monotonic() - start < 1.0
    c.close()


def test_async_batch_runs_in_a_context_of_its_own() -> None:
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="none")
    seen: list[str] = []
    gate = asyncio.Event()

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(var.get())
        await gate.wait()
        body = json.loads(request.content)
        if request.url.path.endswith("/batch"):
            return httpx2.Response(200, json={"replies": [{"publish": {}} for _ in body["commands"]]})
        return httpx2.Response(200, json={"result": {}})

    async def main() -> list[list[str]]:
        callers: list[list[str]] = []

        def batch_context(contexts: list[contextvars.Context]) -> contextlib.AbstractContextManager[Any]:
            callers.append([ctx.run(var.get) for ctx in contexts])
            return contextlib.nullcontext()

        c = cent.AsyncClient(
            ENDPOINT,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
            auto_batch=cent.AutoBatch(max_in_flight=1),
            batch_context=batch_context,
        )

        async def call(name: str) -> None:
            var.set(name)
            await c.publish(channel=name, data=1)

        tasks = [asyncio.create_task(call(f"caller{i}")) for i in range(4)]
        await asyncio.sleep(0.02)
        gate.set()
        await asyncio.gather(*tasks)
        await c.aclose()
        return callers

    callers = asyncio.run(main())
    # The first call went alone, in its caller's context; the batch in none.
    assert seen == ["caller0", "none"]
    assert callers == [["caller1", "caller2", "caller3"]]


def test_sync_batch_context_gets_the_callers() -> None:
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="none")
    gate = threading.Event()
    seen: list[str] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(var.get())
        gate.wait(5)
        body = json.loads(request.content)
        if request.url.path.endswith("/batch"):
            return httpx2.Response(200, json={"replies": [{"publish": {}} for _ in body["commands"]]})
        return httpx2.Response(200, json={"result": {}})

    callers: list[list[str]] = []
    in_batch: list[str] = []

    @contextlib.contextmanager
    def batch_context(contexts: list[contextvars.Context]) -> Iterator[None]:
        callers.append(sorted(ctx.run(var.get) for ctx in contexts))
        token = var.set("batch")
        try:
            yield
        finally:
            var.reset(token)
            in_batch.append(var.get())

    c = cent.Client(
        ENDPOINT,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        auto_batch=cent.AutoBatch(max_in_flight=1),
        batch_context=batch_context,
    )

    def call(name: str) -> None:
        var.set(name)
        c.publish(channel=name, data=1)

    threads = [threading.Thread(target=call, args=(f"caller{i}",)) for i in range(4)]
    threads[0].start()
    time.sleep(0.05)
    for t in threads[1:]:
        t.start()
    time.sleep(0.05)
    gate.set()
    for t in threads:
        t.join(5)
    c.close()
    assert seen == ["caller0", "batch"]
    assert callers == [["caller1", "caller2", "caller3"]]


def test_each_caller_gets_its_own_batch_error() -> None:
    gate = threading.Event()

    def handler(request: httpx2.Request) -> httpx2.Response:
        gate.wait(5)
        return httpx2.Response(503)

    c = cent.Client(
        ENDPOINT,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        auto_batch=cent.AutoBatch(max_in_flight=1),
    )
    errors: list[cent.HTTPError] = []

    def call() -> None:
        try:
            c.publish(channel="x", data=1)
        except cent.HTTPError as e:
            errors.append(e)

    threads = [threading.Thread(target=call) for _ in range(4)]
    threads[0].start()
    time.sleep(0.05)
    for t in threads[1:]:
        t.start()
    time.sleep(0.05)
    gate.set()
    for t in threads:
        t.join(5)
    assert len(errors) == 4
    assert len({id(e) for e in errors}) == 4
    assert all(e.status_code == 503 for e in errors)


def test_cancelled_async_batch_resolves_its_callers() -> None:
    async def hang(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(30)
        raise AssertionError

    async def main() -> list[object]:
        c = cent.AsyncClient(
            ENDPOINT,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(hang)),
            auto_batch=cent.AutoBatch(max_in_flight=1),
        )
        first = asyncio.create_task(c.publish(channel="a", data=1))
        await asyncio.sleep(0.01)
        queued = [asyncio.create_task(c.publish(channel="b", data=1)) for _ in range(2)]
        await asyncio.sleep(0.01)
        first.cancel()  # frees the slot: the queued calls go out as a batch
        await asyncio.sleep(0.01)
        assert c._batcher is not None
        for task in list(c._batcher._tasks):
            task.cancel()
        results = await asyncio.wait_for(asyncio.gather(*queued, return_exceptions=True), timeout=2)
        return list(results)

    results = asyncio.run(main())
    assert all(isinstance(r, cent.CentError) for r in results)


def test_non_ascii_token_fails_as_config() -> None:
    c = cent.Client(
        ENDPOINT, bearer_token_func=lambda: "tök", http_client=httpx2.Client(transport=httpx2.MockTransport(Fake()))
    )
    with pytest.raises(cent.InvalidConfigError, match="printable ASCII"):
        c.publish(channel="x", data=1)


def test_undecodable_reply_is_a_decode_error() -> None:
    def corrupt(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"not gzip at all", headers={"Content-Encoding": "gzip"})

    c = cent.Client(ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(corrupt)))
    with pytest.raises(cent.DecodeError):
        c.publish(channel="x", data=1)
    assert gzip  # the Content-Encoding the reply claims


def test_deeply_nested_reply_is_a_decode_error() -> None:
    def deep(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(200, content=b"[" * 100_000)

    c = cent.Client(ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(deep)))
    with pytest.raises(cent.DecodeError):
        c.publish(channel="x", data=1)


def test_deeply_nested_request_is_a_400() -> None:
    errors: list[Exception] = []
    for h in (
        proxy.ConnectHandler(lambda r, req: proxy.ConnectResult(), on_error=lambda r, e: errors.append(e)),
        endpoints.SubscriptionToken(lambda r, ch: "t", on_error=lambda r, e: errors.append(e)),
    ):
        assert h.handle("POST", {}, b"[" * 100_000).status == 400
    assert len(errors) == 2


def test_bad_call_timeout_is_an_invalid_request() -> None:
    c = cent.Client(ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(Fake())))
    for bad in (-1, "5", True):
        with pytest.raises(cent.InvalidRequestError, match="timeout"):
            c.publish(channel="x", data=1, timeout=bad)  # type: ignore[arg-type]
