"""Automatic batching, blocking and async."""

from __future__ import annotations

import asyncio
import json
import random
import threading
import time
from typing import Any

import httpx2
import pytest

import cent
from tests.conftest import ENDPOINT


class Gate:
    """A fake Centrifugo whose replies wait until released, counting the
    requests in flight."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.in_flight = 0
        self.max_in_flight = 0
        self.requests: list[dict[str, Any]] = []
        self.paths: list[str] = []
        self.open = threading.Event()
        self.fail_batch = False

    def answer(self, method: str, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("channel") == "bad":
            return {"error": {"code": 102, "message": "unknown channel"}}
        return {method: {"offset": int(body.get("channel", "0").split(":")[-1] or 0), "epoch": "e"}}

    def respond(self, request: httpx2.Request) -> httpx2.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        body = json.loads(request.content)
        with self.lock:
            self.requests.append(body)
            self.paths.append(method)
        if method == "batch":
            if self.fail_batch:
                return httpx2.Response(503)
            replies = []
            for cmd in body["commands"]:
                ((m, b),) = cmd.items()
                replies.append(self.answer(m, b))
            return httpx2.Response(200, json={"replies": replies})
        r = self.answer(method, body)
        if "error" in r:
            return httpx2.Response(200, json=r)
        return httpx2.Response(200, json={"result": r[method]})

    def sync_handler(self, request: httpx2.Request) -> httpx2.Response:
        with self.lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            self.open.wait(5)
            return self.respond(request)
        finally:
            with self.lock:
                self.in_flight -= 1

    async def async_handler(self, request: httpx2.Request) -> httpx2.Response:
        with self.lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            # The gate is a threading.Event, shared with the blocking tests.
            while not self.open.is_set():  # noqa: ASYNC110
                await asyncio.sleep(0.001)
            # Requests overlap, as on a network.
            await asyncio.sleep(0.001)
            return self.respond(request)
        finally:
            with self.lock:
                self.in_flight -= 1


def pub(i: int | str) -> dict[str, Any]:
    return {"channel": f"ch:{i}" if isinstance(i, int) else i, "data": 1}


def sync_client(gate: Gate, **kw: Any) -> cent.Client:
    http = httpx2.Client(transport=httpx2.MockTransport(gate.sync_handler))
    return cent.Client(ENDPOINT, http_client=http, auto_batch=cent.AutoBatch(max_in_flight=2), **kw)


def async_client(gate: Gate, **kw: Any) -> cent.AsyncClient:
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(gate.async_handler))
    return cent.AsyncClient(ENDPOINT, http_client=http, auto_batch=cent.AutoBatch(max_in_flight=2), **kw)


def test_below_the_cap_calls_go_alone() -> None:
    gate = Gate()
    gate.open.set()
    c = sync_client(gate)
    assert c.publish(**pub(1)).offset == 1
    assert c.publish(**pub(2)).offset == 2
    assert gate.paths == ["publish", "publish"]


def test_at_the_cap_calls_batch() -> None:
    gate = Gate()
    infos: list[cent.RequestInfo] = []
    c = sync_client(gate, on_request=infos.append)
    results: dict[int, Any] = {}

    def run(i: int) -> None:
        try:
            results[i] = c.publish(**(pub(i) if i != 5 else pub("bad")))
        except Exception as e:
            results[i] = e

    threads = [threading.Thread(target=run, args=(i,)) for i in range(1, 8)]
    for t in threads:
        t.start()
    time.sleep(0.1)  # two in flight, five queued
    gate.open.set()
    for t in threads:
        t.join(5)
    assert gate.max_in_flight == 2
    assert gate.paths.count("batch") >= 1
    batch = next(r for r, p in zip(gate.requests, gate.paths, strict=True) if p == "batch")
    assert batch["parallel"] is True
    for i in range(1, 8):
        if i == 5:
            assert isinstance(results[i], cent.UnknownChannelError)
        else:
            assert results[i].offset == i
    auto = [i for i in infos if i.auto_batch]
    assert auto
    assert auto[0].method == "batch"


def test_batch_failing_as_a_whole_fails_its_calls() -> None:
    gate = Gate()
    gate.fail_batch = True
    c = sync_client(gate)
    errors: list[Exception] = []

    def run(i: int) -> None:
        try:
            c.publish(**pub(i))
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=run, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    time.sleep(0.1)
    gate.open.set()
    for t in threads:
        t.join(5)
    assert errors
    assert all(isinstance(e, cent.HTTPError) and e.status_code == 503 for e in errors)


def test_queued_call_timing_out_is_not_sent() -> None:
    gate = Gate()
    c = sync_client(gate)
    holders = [threading.Thread(target=c.publish, kwargs=pub(i)) for i in (1, 2)]
    for t in holders:
        t.start()
    time.sleep(0.05)
    with pytest.raises(cent.CentTimeoutError, match="before it was sent"):
        c.publish(**pub(3), timeout=0.05)
    gate.open.set()
    for t in holders:
        t.join(5)
    c.close(timeout=5)
    assert all(b.get("channel") != "ch:3" for b in gate.requests)
    assert all("ch:3" not in json.dumps(b) for b in gate.requests)


def test_close_waits_for_batches() -> None:
    gate = Gate()
    c = sync_client(gate)
    threads = [threading.Thread(target=c.publish, kwargs=pub(i)) for i in range(5)]
    for t in threads:
        t.start()
    time.sleep(0.05)
    with pytest.raises(cent.CentTimeoutError):
        c.close(timeout=0.05)
    gate.open.set()
    c.close(timeout=5)
    for t in threads:
        t.join(5)


@pytest.mark.parametrize(
    ("opts", "msg"),
    [({"max_in_flight": 0}, "max_in_flight"), ({"max_in_flight": 2, "max_batch_size": 1}, "max_batch_size")],
)
def test_auto_batch_config(opts: dict[str, int], msg: str) -> None:
    with pytest.raises(cent.InvalidConfigError, match=msg):
        cent.AutoBatch(**opts)
    with pytest.raises(cent.InvalidConfigError):
        cent.Client(ENDPOINT, auto_batch={"max_in_flight": 2})  # type: ignore[arg-type]


def test_batches_are_sent_by_kept_threads_which_close_stops() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        time.sleep(0.001)
        body = json.loads(request.content)
        if request.url.path.endswith("/batch"):
            return httpx2.Response(200, json={"replies": [{"info": {}} for _ in body["commands"]]})
        return httpx2.Response(200, json={"result": {}})

    batches = []
    c = cent.Client(
        ENDPOINT,
        http_client=httpx2.Client(transport=httpx2.MockTransport(handler)),
        auto_batch=cent.AutoBatch(max_in_flight=2),
        on_request=lambda i: batches.append(i) if i.auto_batch else None,
    )

    before = {t.ident for t in threading.enumerate()}

    def senders() -> int:
        return sum(1 for t in threading.enumerate() if t.name == "pycent-autobatch" and t.ident not in before)

    peak = 0
    stop = threading.Event()

    def sample() -> None:
        nonlocal peak
        while not stop.is_set():
            peak = max(peak, senders())
            time.sleep(0.001)

    sampler = threading.Thread(target=sample)
    sampler.start()
    callers = [threading.Thread(target=lambda: [c.info() for _ in range(30)]) for _ in range(12)]
    for t in callers:
        t.start()
    for t in callers:
        t.join()
    stop.set()
    sampler.join()
    assert batches
    assert 1 <= peak <= 2  # at most one sender per slot, however many batches
    c.close(timeout=5)
    deadline = time.monotonic() + 5
    while senders() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert senders() == 0


def test_idle_senders_end(monkeypatch: pytest.MonkeyPatch) -> None:
    from cent import _autobatch

    monkeypatch.setattr(_autobatch, "_WORKER_IDLE", 0.05)
    gate = threading.Event()

    def handler(request: httpx2.Request) -> httpx2.Response:
        gate.wait(5)
        body = json.loads(request.content)
        if request.url.path.endswith("/batch"):
            return httpx2.Response(200, json={"replies": [{"info": {}} for _ in body["commands"]]})
        return httpx2.Response(200, json={"result": {}})

    before = {t.ident for t in threading.enumerate()}

    def senders() -> int:
        return sum(1 for t in threading.enumerate() if t.name == "pycent-autobatch" and t.ident not in before)

    c = cent.Client(
        ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)), auto_batch=cent.AutoBatch(1)
    )
    first = threading.Thread(target=c.info)
    first.start()
    time.sleep(0.05)
    queued = threading.Thread(target=c.info)
    queued.start()
    time.sleep(0.05)
    gate.set()
    first.join()
    queued.join()
    assert senders() == 1  # sent the batch, still there
    deadline = time.monotonic() + 5
    while senders() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert senders() == 0  # ended idle, the client open


def test_stress_sync() -> None:
    gate = Gate()
    gate.open.set()
    http = httpx2.Client(transport=httpx2.MockTransport(gate.sync_handler))
    c = cent.Client(ENDPOINT, http_client=http, auto_batch=cent.AutoBatch(max_in_flight=3, max_batch_size=5))
    bad: list[str] = []

    def run(worker: int) -> None:
        for n in range(30):
            i = worker * 1000 + n
            if random.random() < 0.2:
                time.sleep(0.001)
            res = c.publish(**pub(i))
            if res.offset != i:
                bad.append(f"{i}: {res.offset}")

    threads = [threading.Thread(target=run, args=(w,)) for w in range(1, 13)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    c.close(timeout=5)
    assert bad == []
    assert gate.max_in_flight <= 3
    sizes = [len(b["commands"]) for b, p in zip(gate.requests, gate.paths, strict=True) if p == "batch"]
    assert all(2 <= s <= 5 or s == 1 for s in sizes)


async def test_async_batches() -> None:
    gate = Gate()
    infos: list[cent.RequestInfo] = []
    c = async_client(gate, on_request=infos.append)
    tasks = [asyncio.create_task(c.publish(**(pub(i) if i != 4 else pub("bad")))) for i in range(1, 9)]
    await asyncio.sleep(0.05)
    gate.open.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    assert gate.max_in_flight == 2
    assert "batch" in gate.paths
    for i, r in enumerate(results, 1):
        if i == 4:
            assert isinstance(r, cent.UnknownChannelError)
        else:
            assert isinstance(r, cent.PublishResult)
            assert r.offset == i
    await c.aclose(timeout=5)


async def test_async_queued_call_cancelled_is_not_sent() -> None:
    gate = Gate()
    c = async_client(gate)
    holders = [asyncio.create_task(c.publish(**pub(i))) for i in (1, 2)]
    await asyncio.sleep(0.02)
    queued = asyncio.create_task(c.publish(**pub(3)))
    await asyncio.sleep(0.02)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    with pytest.raises(cent.CentTimeoutError, match="before it was sent"):
        await c.publish(**pub(4), timeout=0.02)
    gate.open.set()
    await asyncio.gather(*holders)
    await c.aclose(timeout=5)
    sent = json.dumps(gate.requests)
    assert "ch:3" not in sent
    assert "ch:4" not in sent


async def test_stress_async() -> None:
    gate = Gate()
    gate.open.set()
    http = httpx2.AsyncClient(transport=httpx2.MockTransport(gate.async_handler))
    c = cent.AsyncClient(ENDPOINT, http_client=http, auto_batch=cent.AutoBatch(max_in_flight=3, max_batch_size=4))
    bad: list[str] = []

    async def run(worker: int) -> None:
        for n in range(40):
            i = worker * 1000 + n
            if random.random() < 0.3:
                await asyncio.sleep(0)
            res = await c.publish(**pub(i))
            if res.offset != i:
                bad.append(f"{i}: {res.offset}")

    await asyncio.gather(*(run(w) for w in range(1, 21)))
    await c.aclose(timeout=5)
    assert bad == []
    assert gate.max_in_flight <= 3
    assert "batch" in gate.paths
