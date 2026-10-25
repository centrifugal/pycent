"""The API client, blocking and async, against a fake Centrifugo."""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx2
import pytest

import cent
from tests.conftest import ENDPOINT, Fake

pytestmark = pytest.mark.filterwarnings("error")


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


def test_publish(api: Api, fake: Fake) -> None:
    res = api.publish(cent.PublishRequest(channel="news", data={"text": "hi"}, idempotency_key="k1"))
    assert res == cent.PublishResult(offset=1, epoch="e1")
    (req,) = fake.requests
    assert str(req.url) == ENDPOINT + "/publish"
    assert req.method == "POST"
    assert req.headers["X-API-Key"] == "key"
    assert req.headers["Content-Type"] == "application/json"
    assert req.headers["User-Agent"] == "pycent/6"
    # Zero values are not sent; names are the protos'.
    assert json.loads(req.content) == {"channel": "news", "data": {"text": "hi"}, "idempotency_key": "k1"}


def test_every_method_reaches_its_endpoint(api: Api, fake: Fake) -> None:
    methods = [m for m in cent._api.METHODS if m not in ("batch", "broadcast")]
    for m in methods:
        request_type = next(t for t in cent._api.REQUESTS if m == t.api_method)
        req = request_type()
        if m == "publish":
            req = cent.PublishRequest(channel="ch", data=1)
        getattr(api, m)(req)
    paths = [r.url.path.rsplit("/", 1)[-1] for r in fake.requests]
    assert paths == methods


def test_empty_request_methods_take_no_argument(api: Api, fake: Fake) -> None:
    fake.on("info", {"nodes": [{"uid": "n1", "name": "node", "num_clients": 3}]})
    res = api.info()
    assert res.nodes[0].uid == "n1"
    assert res.nodes[0].num_clients == 3


def test_api_error_by_code(api: Api, fake: Fake) -> None:
    fake.on("publish", cent.ApiError(102, "unknown channel"))
    with pytest.raises(cent.UnknownChannelError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert e.value.code == 102
    assert not cent.retryable(e.value)
    assert str(e.value) == "unknown channel (code 102)"


def test_unknown_code_is_api_error(api: Api, fake: Fake) -> None:
    fake.on("publish", cent.ApiError(9999, "new"))
    with pytest.raises(cent.ApiError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert type(e.value) is cent.ApiError
    assert e.value.code == 9999


def test_temporary_error_is_retryable(api: Api, fake: Fake) -> None:
    fake.on("publish", cent.ApiError(108, "not available", temporary=True))
    with pytest.raises(cent.NotAvailableError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert e.value.temporary
    assert cent.retryable(e.value)


def test_internal_error_is_retryable_without_temporary(api: Api, fake: Fake) -> None:
    fake.on("publish", cent.ApiError(100, "internal"))
    with pytest.raises(cent.InternalError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert cent.retryable(e.value)


@pytest.mark.parametrize(
    ("status", "cls", "retry"),
    [(401, cent.UnauthorizedError, False), (403, cent.HTTPError, False), (503, cent.HTTPError, True)],
)
def test_http_errors(api: Api, fake: Fake, status: int, cls: type[Exception], retry: bool) -> None:
    fake.on("publish", httpx2.Response(status, text="go away", headers={"Retry-After": "3"}))
    with pytest.raises(cls) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    err = e.value
    assert isinstance(err, cent.HTTPError)
    assert err.status_code == status
    assert err.body == b"go away"
    assert err.headers["Retry-After"] == "3"
    assert cent.retryable(err) is retry
    if status == 401:
        assert "check the credentials" in str(err)


def test_429_is_retryable(api: Api, fake: Fake) -> None:
    fake.on("publish", httpx2.Response(429, text=""))
    with pytest.raises(cent.HTTPError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert cent.retryable(e.value)


def test_error_body_is_bounded(api: Api, fake: Fake) -> None:
    fake.on("publish", httpx2.Response(502, content=b"x" * 100_000))
    with pytest.raises(cent.HTTPError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert len(e.value.body) == 512


def test_redirect_is_not_followed(api: Api, fake: Fake) -> None:
    fake.on("publish", httpx2.Response(307, headers={"Location": "https://elsewhere.test/api/publish"}))
    with pytest.raises(cent.HTTPError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert e.value.status_code == 307
    assert "does not follow" in str(e.value)
    assert len(fake.requests) == 1


def test_404_hints(api: Api, fake: Fake) -> None:
    fake.on("connections", httpx2.Response(404))
    fake.on("publish", httpx2.Response(404))
    with pytest.raises(cent.HTTPError) as e:
        api.connections(cent.ConnectionsRequest(user="u"))
    assert "connections is a Centrifugo PRO method" in str(e.value)
    with pytest.raises(cent.HTTPError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert "is api_endpoint the API base URL" in str(e.value)


def test_transport_error_mode(api: Api, fake: Fake) -> None:
    fake.on("publish", httpx2.Response(400, json={"code": 102, "message": "unknown channel"}))
    with pytest.raises(cent.UnknownChannelError):
        api.publish(cent.PublishRequest(channel="x", data=1))


@pytest.mark.parametrize(
    ("status", "body"),
    [(429, {"code": 429}), (503, {"code": 102}), (400, {"code": 42}), (500, {"message": "x"})],
)
def test_gateway_json_errors_stay_http_errors(api: Api, fake: Fake, status: int, body: dict[str, Any]) -> None:
    fake.on("publish", httpx2.Response(status, json=body))
    with pytest.raises(cent.HTTPError):
        api.publish(cent.PublishRequest(channel="x", data=1))


@pytest.mark.parametrize("body", [b"<html>nope</html>", b"[1]", b'{"result": 5}', b'{"result": {"offset": "1"}}'])
def test_decode_error(api: Api, fake: Fake, body: bytes) -> None:
    fake.on("publish", httpx2.Response(200, content=body))
    with pytest.raises(cent.DecodeError) as e:
        api.publish(cent.PublishRequest(channel="x", data=1))
    assert not cent.retryable(e.value)


def test_network_error(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    def refuse(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("connection refused", request=request)

    a = new_api(http_client=_http(kind, refuse))
    with pytest.raises(cent.NetworkError) as e:
        a.publish(cent.PublishRequest(channel="x", data=1))
    assert isinstance(e.value.__cause__, httpx2.ConnectError)
    assert cent.retryable(e.value)


def test_timeout_error(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    def slow(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ReadTimeout("timed out", request=request)

    a = new_api(http_client=_http(kind, slow))
    with pytest.raises(cent.CentTimeoutError) as e:
        a.publish(cent.PublishRequest(channel="x", data=1))
    assert isinstance(e.value, TimeoutError)
    assert cent.retryable(e.value)


def _http(kind: str, handler: Callable[[httpx2.Request], httpx2.Response]) -> Any:
    t = httpx2.MockTransport(handler)
    return httpx2.AsyncClient(transport=t) if kind == "async" else httpx2.Client(transport=t)


def test_timeout_bounds_the_call(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    """A reply which trickles in is cut at the deadline: the call has one
    deadline whatever the HTTP library's own timeouts are per read."""

    class Trickle(httpx2.SyncByteStream, httpx2.AsyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for _ in range(50):
                time.sleep(0.02)
                yield b" "

        async def __aiter__(self) -> Any:
            for _ in range(50):
                await asyncio.sleep(0.02)
                yield b" "

    a = new_api(http_client=_http(kind, lambda r: httpx2.Response(200, stream=Trickle())))
    start = time.monotonic()
    with pytest.raises(cent.CentTimeoutError):
        a.publish(cent.PublishRequest(channel="x", data=1), timeout=0.2)
    assert time.monotonic() - start < 0.5


def test_validation(api: Api, fake: Fake) -> None:
    cases: list[tuple[cent.PublishRequest | cent.BroadcastRequest, str]] = [
        (cent.PublishRequest(data=1), "channel is required"),
        (cent.PublishRequest(channel="x"), "data or b64data is required"),
        (cent.BroadcastRequest(data=1), "channels is required"),
        (cent.BroadcastRequest(channels=["a", ""], data=1), "channels[1] is empty"),
    ]
    for req, msg in cases:
        with pytest.raises(cent.InvalidRequestError, match=re.escape(msg)):
            getattr(api, req.api_method)(req)
    assert fake.requests == []


def test_not_a_request(api: Api) -> None:
    with pytest.raises(TypeError):
        api.publish({"channel": "x"})


# Payloads.


@pytest.mark.parametrize(
    ("data", "wire"),
    [
        ({}, "{}"),
        ({"0": "a"}, '{"0":"a"}'),
        ([], "[]"),
        ("hello", '"hello"'),
        (2**64 + 1, str(2**64 + 1)),
        (1.0, "1.0"),
        (None, None),
        (False, "false"),
        (cent.RawJSON('{"n": 1.50, "big": 18446744073709551617}'), '{"n": 1.50, "big": 18446744073709551617}'),
        (cent.RawJSON("null"), "null"),
        ({"text": "żółw  "}, '{"text":"żółw  "}'),
    ],
)
def test_payload_encoding(api: Api, fake: Fake, data: Any, wire: str | None) -> None:
    req = cent.PublishRequest(channel="ch", data=data, b64data="" if data is not None else "Zm9v")
    api.publish(req)
    raw = fake.requests[0].content.decode()
    if wire is None:
        assert '"data"' not in raw
    else:
        assert '"data":' + wire in raw


@pytest.mark.parametrize(
    ("data", "msg"),
    [
        (float("nan"), "not a JSON number"),
        (float("inf"), "not a JSON number"),
        ({"x": float("nan")}, "cannot be encoded"),
        (b"bytes", "b64data"),
        ({"b": b"x"}, "b64data"),
        ({1j}, "cannot be encoded"),
        ("\ud800", "not valid UTF-8"),
    ],
)
def test_payload_refused_before_sending(api: Api, fake: Fake, data: Any, msg: str) -> None:
    with pytest.raises(cent.InvalidRequestError, match=msg):
        api.publish(cent.PublishRequest(channel="ch", data=data))
    assert fake.requests == []


@pytest.mark.parametrize("text", ["{", "NaN", '{"a": Infinity}', b"\xff"])
def test_raw_json_checked(text: str | bytes) -> None:
    with pytest.raises(cent.InvalidRequestError):
        cent.RawJSON(text)


def test_payload_round_trip(api: Api, fake: Fake) -> None:
    """A payload from a reply sent back unchanged is the same JSON value."""
    original = '{"a":{},"b":{"0":"a"},"c":18446744073709551617,"d":1.0,"e":[1.5,-0.0],"f":"x"}'
    fake.on(
        "history",
        httpx2.Response(
            200, content=b'{"result":{"publications":[{"data":' + original.encode() + b',"offset":7}],"offset":7}}'
        ),
    )
    hist = api.history(cent.HistoryRequest(channel="ch", limit=1))
    pub = hist.publications[0]
    assert pub.offset == 7
    api.publish(cent.PublishRequest(channel="ch", data=pub.data))
    sent = json.loads(fake.requests[-1].content)["data"]
    assert json.dumps(sent, separators=(",", ":")) == original
    assert '"d":1.0' in fake.requests[-1].content.decode()


def test_bool_value_fields(api: Api, fake: Fake) -> None:
    api.subscribe(
        cent.SubscribeRequest(
            channel="ch", user="u", override=cent.SubscribeOptionOverride(presence=False, join_leave=None)
        )
    )
    api.subscribe(cent.SubscribeRequest(channel="ch", user="u", override=cent.SubscribeOptionOverride()))
    first, second = fake.bodies("subscribe")
    assert first["override"] == {"presence": {"value": False}}
    # An override with nothing set is not sent.
    assert "override" not in second


# Broadcast.


def test_broadcast(api: Api) -> None:
    res = api.broadcast(cent.BroadcastRequest(channels=["a", "b"], data={"x": 1}, idempotency_key="k"))
    assert res.replied
    assert res.attempts == 1
    assert res.idempotency_key == "k"
    assert [c.channel for c in res.channels] == ["a", "b"]
    assert all(c.result == cent.PublishResult(offset=1, epoch="e1") and c.error is None for c in res.channels)
    assert res.failed() == []


def test_broadcast_partial_failure(api: Api) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast(cent.BroadcastRequest(channels=["a", "bad:1", "b", "full:1"], data=1))
    err = e.value
    assert err.total == 4
    assert [f.channel for f in err.failed] == ["bad:1", "full:1"]
    assert isinstance(err.failed[0].error, cent.UnknownChannelError)
    assert isinstance(err.failed[1].error, cent.NotAvailableError)
    # A partial error is not an ApiError of its parts.
    assert not isinstance(err, cent.ApiError)
    assert err.result.replied
    assert len(err.result.channels) == 4
    assert err.result.channels[2].result == cent.PublishResult(offset=1, epoch="e1")
    assert str(err) == (
        "broadcast: 2 of 4 channels failed, 2 got the publication: "
        "bad:1: unknown channel (code 102); full:1: not available (code 108)"
    )
    assert not cent.retryable(err)


def test_broadcast_into_one_unknown_channel_is_a_partial_error(api: Api) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast(cent.BroadcastRequest(channels=["bad:1"], data=1))
    assert e.value.total == 1


def test_broadcast_retryable_channels(api: Api) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast(cent.BroadcastRequest(channels=["a", "flaky:1", "bad:1"], data=1))
    assert e.value.retryable_channels() == ["flaky:1"]
    assert cent.retryable(e.value)
    assert str(e.value).endswith("(retry only retryable_channels(), with the same idempotency_key)")


def test_broadcast_failure_message_is_bounded(api: Api) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast(cent.BroadcastRequest(channels=[f"bad:{i}" for i in range(100)], data=1))
    assert "100 of 100 channels failed" in str(e.value)
    assert str(e.value).endswith("and 97 more")


def test_broadcast_reply_count_mismatch(api: Api, fake: Fake) -> None:
    fake.on("broadcast", {"responses": [{"result": {}}]})
    with pytest.raises(cent.DecodeError):
        api.broadcast(cent.BroadcastRequest(channels=["a", "b"], data=1))


def test_broadcast_with_retry(api: Api, fake: Fake) -> None:
    calls: list[list[str]] = []

    def flaky_once(_m: str, body: dict[str, Any]) -> Any:
        calls.append(body["channels"])
        out = []
        for ch in body["channels"]:
            if ch == "flaky" and len(calls) == 1:
                out.append({"error": {"code": 100, "message": "internal", "temporary": True}})
            else:
                out.append({"result": {"offset": len(calls), "epoch": "e"}})
        return {"responses": out}

    fake.on("broadcast", flaky_once)
    seen: list[cent.BroadcastAttempt] = []

    def on_err(a: cent.BroadcastAttempt) -> float:
        seen.append(a)
        return 0.0

    res = api.broadcast_with_retry(cent.BroadcastRequest(channels=["a", "flaky", "b"], data=1), on_attempt_error=on_err)
    assert calls == [["a", "flaky", "b"], ["flaky"]]
    assert res.attempts == 2
    assert [c.attempts for c in res.channels] == [1, 2, 1]
    assert [c.result.offset for c in res.channels if c.result] == [1, 2, 1]
    keys = {b["idempotency_key"] for b in fake.bodies("broadcast")}
    assert len(keys) == 1
    assert res.idempotency_key in keys
    assert res.idempotency_key.startswith("pycent-")
    assert seen[0].attempt == 1
    assert [c.channel for c in seen[0].retry] == ["flaky"]


def test_broadcast_with_retry_stops_on_permanent_failure(api: Api, fake: Fake) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast_with_retry(cent.BroadcastRequest(channels=["a", "bad:1"], data=1))
    assert len(fake.requests) == 1
    assert e.value.result.attempts == 1


def test_broadcast_with_retry_gives_up(api: Api, fake: Fake) -> None:
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        api.broadcast_with_retry(
            cent.BroadcastRequest(channels=["a", "flaky:1"], data=1), max_attempts=3, on_attempt_error=lambda a: 0.0
        )
    assert len(fake.requests) == 3
    assert [f.channel for f in e.value.failed] == ["flaky:1"]
    assert e.value.result.channels[1].attempts == 3
    assert e.value.result.channels[0].attempts == 1


def test_broadcast_with_retry_stopped_by_callback(api: Api) -> None:
    class Stop(Exception):
        pass

    def stop(a: cent.BroadcastAttempt) -> float:
        raise Stop

    with pytest.raises(Stop) as e:
        api.broadcast_with_retry(cent.BroadcastRequest(channels=["a", "flaky:1"], data=1), on_attempt_error=stop)
    cause = e.value.__cause__
    assert isinstance(cause, cent.BroadcastFailedChannelsError)
    assert cause.result.channels[0].error is None


def test_broadcast_with_retry_whole_failure(api: Api, fake: Fake) -> None:
    fake.on("broadcast", httpx2.Response(503))
    with pytest.raises(cent.HTTPError):
        api.broadcast_with_retry(cent.BroadcastRequest(channels=["a"], data=1), on_attempt_error=lambda a: 0.0)
    assert len(fake.requests) == 2


@pytest.mark.parametrize("opts", [{"max_attempts": 0}, {"attempt_timeout": -1}])
def test_broadcast_with_retry_options(api: Api, fake: Fake, opts: dict[str, Any]) -> None:
    with pytest.raises(cent.InvalidRequestError):
        api.broadcast_with_retry(cent.BroadcastRequest(channels=["a"], data=1), **opts)
    assert fake.requests == []


def test_exponential_backoff() -> None:
    b = cent.exponential_backoff(0.1, 1.0)
    for attempt, top in [(1, 0.1), (2, 0.2), (3, 0.4), (4, 0.8), (5, 1.0), (100, 1.0), (0, 0.1)]:
        for _ in range(20):
            d = b(attempt)
            assert top / 2 <= d <= top
    assert cent.exponential_backoff(-1, -5)(3) == 0
    assert 0.5 <= cent.exponential_backoff(1, 0.5)(1) <= 1.0


# Batches.


def test_batch(api: Api, fake: Fake) -> None:
    b = api.client.new_batch()
    pub = b.publish(cent.PublishRequest(channel="a", data=1))
    stats = b.presence_stats(cent.PresenceStatsRequest(channel="a"))
    bc = b.broadcast(cent.BroadcastRequest(channels=["x", "y"], data=2))
    with pytest.raises(cent.BatchNotSentError):
        pub.result()
    res = api.send(b)
    assert res.replied
    assert res.failed() == []
    assert pub.result() == cent.PublishResult(offset=1, epoch="e1")
    assert stats.result() == cent.PresenceStatsResult()
    assert len(bc.result().channels) == 2
    (body,) = fake.bodies("batch")
    assert body == {
        "commands": [
            {"publish": {"channel": "a", "data": 1}},
            {"presence_stats": {"channel": "a"}},
            {"broadcast": {"channels": ["x", "y"], "data": 2}},
        ]
    }
    with pytest.raises(cent.BatchSentError):
        api.send(b)
    with pytest.raises(RuntimeError):
        b.publish(cent.PublishRequest(channel="a", data=1))


def test_batch_parallel(api: Api, fake: Fake) -> None:
    b = api.client.new_batch(parallel=True)
    b.publish(cent.PublishRequest(channel="a", data=1))
    api.send(b)
    assert fake.bodies("batch")[0]["parallel"] is True


def test_batch_partial_failure(api: Api, fake: Fake) -> None:
    fake.on("presence", cent.ApiError(108, "not available"))
    b = api.client.new_batch()
    pub = b.publish(cent.PublishRequest(channel="a", data=1))
    pres = b.presence(cent.PresenceRequest(channel="a"))
    bc = b.broadcast(cent.BroadcastRequest(channels=["x", "bad:1"], data=2))
    with pytest.raises(cent.BatchFailedCommandsError) as e:
        api.send(b)
    err = e.value
    assert [(f.index, f.method) for f in err.failed] == [(1, "presence"), (2, "broadcast")]
    assert err.result.replied
    assert pub.result().offset == 1
    with pytest.raises(cent.NotAvailableError):
        pres.result()
    with pytest.raises(cent.BroadcastFailedChannelsError) as be:
        bc.result()
    # The batch error holds the very error the pending raises.
    assert err.failed[1].error is be.value
    assert str(err).startswith("batch: 2 of 3 commands failed, 1 succeeded: #1 presence: not available")


def test_batch_pro_method_on_oss_hints(api: Api, fake: Fake) -> None:
    fake.on("connections", cent.ApiError(104, "not found"))
    fake.on("history", cent.ApiError(104, "not found"))
    b = api.client.new_batch()
    conns = b.connections(cent.ConnectionsRequest(user="u"))
    hist = b.history(cent.HistoryRequest(channel="x"))
    with pytest.raises(cent.BatchFailedCommandsError):
        api.send(b)
    with pytest.raises(cent.NotFoundError, match="connections is a Centrifugo PRO method"):
        conns.result()
    with pytest.raises(cent.NotFoundError) as e:
        hist.result()
    assert "PRO" not in str(e.value)


def test_batch_whole_failure(api: Api, fake: Fake) -> None:
    fake.on("batch", httpx2.Response(500))
    b = api.client.new_batch()
    pub = b.publish(cent.PublishRequest(channel="a", data=1))
    with pytest.raises(cent.HTTPError):
        api.send(b)
    with pytest.raises(cent.HTTPError):
        pub.result()


def test_batch_invalid_command_fails_before_sending(api: Api, fake: Fake) -> None:
    b = api.client.new_batch()
    b.publish(cent.PublishRequest(channel="a", data=1))
    p = b.publish(cent.PublishRequest(channel="a", data=float("nan")))
    with pytest.raises(cent.InvalidRequestError, match="batch command #1"):
        api.send(b)
    with pytest.raises(cent.InvalidRequestError):
        p.result()
    assert fake.requests == []


def test_batch_reply_count_mismatch(api: Api, fake: Fake) -> None:
    fake.on("batch", httpx2.Response(200, json={"replies": [{}]}))
    b = api.client.new_batch()
    b.publish(cent.PublishRequest(channel="a", data=1))
    b.publish(cent.PublishRequest(channel="b", data=1))
    with pytest.raises(cent.DecodeError):
        api.send(b)


def test_empty_batch(api: Api, fake: Fake) -> None:
    assert api.send(api.client.new_batch()).replied
    assert fake.requests == []
    api.close()
    with pytest.raises(cent.ClosedError):
        api.send(api.client.new_batch())


# Commands.


def test_new_command() -> None:
    cmd = cent.new_command(cent.PublishRequest(channel="news", data=cent.RawJSON('{"n": 1.0}')))
    assert cmd.method == "publish"
    assert cmd.payload == '{"channel":"news","data":{"n": 1.0}}'
    assert json.loads(cmd.to_json()) == {"method": "publish", "payload": {"channel": "news", "data": {"n": 1.0}}}
    with pytest.raises(cent.InvalidRequestError):
        cent.new_command(cent.PublishRequest(data=1))


# Configuration.


@pytest.mark.parametrize(
    ("opts", "msg"),
    [
        ({}, "api_endpoint is required"),
        ({"api_endpoint": "localhost:8000/api"}, "absolute http"),
        ({"api_endpoint": "ftp://x/api"}, "absolute http"),
        ({"api_endpoint": "http:///api"}, "no host"),
        ({"api_endpoint": "http://x/api?q=1"}, "query"),
        ({"api_endpoint": "http://u:p@x/api"}, "credentials"),
        ({"api_endpoint": "http://x/api/publish"}, "ends with the method"),
        ({"api_endpoint": ENDPOINT, "api_endpoint_func": lambda: ENDPOINT}, "not both"),
        ({"api_endpoint": ENDPOINT, "api_key": "k", "bearer_token_func": lambda: "t"}, "not both"),
        ({"api_endpoint": ENDPOINT, "api_key": "k\n"}, "printable ASCII"),
        ({"api_endpoint": ENDPOINT, "api_key": "clé"}, "printable ASCII"),
        ({"api_endpoint_func": 123}, "callable"),
        ({"api_endpoint": ENDPOINT, "bearer_token_func": "token"}, "callable"),
        ({"api_endpoint": ENDPOINT, "headers": {"X-Api-Key": "k"}}, "use api_key"),
        ({"api_endpoint": ENDPOINT, "headers": {"authorization": "x"}}, "bearer_token_func"),
        ({"api_endpoint": ENDPOINT, "headers": {"Content-Type": "x"}}, "Content-Type"),
        ({"api_endpoint": ENDPOINT, "headers": {"Bad Name": "x"}}, "not a valid HTTP header name"),
        ({"api_endpoint": ENDPOINT, "headers": {"X-A": "a\r\nb"}}, "printable ASCII"),
        ({"api_endpoint": ENDPOINT, "headers": {"X-A": "é"}}, "printable ASCII"),
        ({"api_endpoint": ENDPOINT, "request_timeout": -1}, "positive"),
        ({"api_endpoint": ENDPOINT, "http_client": httpx2.AsyncClient()}, "must be an httpx2.Client"),
    ],
)
def test_invalid_config(opts: dict[str, Any], msg: str) -> None:
    with pytest.raises(cent.InvalidConfigError, match=msg):
        cent.Client(**opts)


def test_httpx_client_refused_with_the_fix() -> None:
    """An httpx client - httpx2's predecessor, which an agent trained on older
    code may reach for - is refused with the fix in the message."""
    httpx = pytest.importorskip("httpx")
    with pytest.raises(cent.InvalidConfigError, match=r"cent uses httpx2.*import httpx2, and pass httpx2.Client"):
        cent.Client(ENDPOINT, http_client=httpx.Client())
    with pytest.raises(cent.InvalidConfigError, match=r"httpx2.AsyncClient"):
        cent.AsyncClient(ENDPOINT, http_client=httpx.AsyncClient())


def test_trailing_slash_dropped(fake: Fake) -> None:
    c = cent.Client(ENDPOINT + "/", http_client=httpx2.Client(transport=httpx2.MockTransport(fake)))
    c.publish(cent.PublishRequest(channel="x", data=1))
    assert str(fake.requests[0].url) == ENDPOINT + "/publish"


def test_headers_and_user_agent(new_api: Callable[..., Api], fake: Fake) -> None:
    a = new_api(headers={"X-Tenant": "t1", "User-Agent": "mine/1"})
    a.publish(cent.PublishRequest(channel="x", data=1))
    h = fake.requests[0].headers
    assert h["X-Tenant"] == "t1"
    assert h["User-Agent"] == "mine/1"
    assert "X-API-Key" not in h


def test_callers_http_client_is_not_changed(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    http = _http(kind, fake)
    before = dict(http.headers)
    a = new_api(http_client=http, api_key="secret")
    a.publish(cent.PublishRequest(channel="x", data=1))
    assert dict(http.headers) == before
    assert fake.requests[0].headers["X-API-Key"] == "secret"


def test_endpoint_and_token_funcs(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    tokens = iter(["t1", "t2"])

    if kind == "async":

        async def token() -> str:
            return next(tokens)

        async def endpoint() -> str:
            return ENDPOINT

        a = new_api(api_endpoint=None, api_endpoint_func=endpoint, bearer_token_func=token)
    else:
        a = new_api(api_endpoint=None, api_endpoint_func=lambda: ENDPOINT, bearer_token_func=lambda: next(tokens))
    a.publish(cent.PublishRequest(channel="x", data=1))
    a.publish(cent.PublishRequest(channel="x", data=1))
    assert [r.headers["Authorization"] for r in fake.requests] == ["Bearer t1", "Bearer t2"]


@pytest.mark.parametrize("token", ["", "a\nb"])
def test_bad_token_fails_before_sending(new_api: Callable[..., Api], kind: str, fake: Fake, token: str) -> None:
    a = new_api(bearer_token_func=lambda: token)
    with pytest.raises(cent.InvalidConfigError):
        a.publish(cent.PublishRequest(channel="x", data=1))
    assert fake.requests == []


def test_bad_endpoint_from_func(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    a = new_api(api_endpoint=None, api_endpoint_func=lambda: "http://x/api/publish")
    with pytest.raises(cent.InvalidConfigError, match="api_endpoint_func"):
        a.publish(cent.PublishRequest(channel="x", data=1))


def test_endpoint_func_error_propagates(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    def down() -> str:
        raise ConnectionRefusedError("discovery is down")

    a = new_api(api_endpoint=None, api_endpoint_func=down)
    with pytest.raises(ConnectionRefusedError):
        a.publish(cent.PublishRequest(channel="x", data=1))


# Observability.


def test_on_request(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    infos: list[cent.RequestInfo] = []
    a = new_api(on_request=infos.append)
    a.publish(cent.PublishRequest(channel="x", data=1))
    fake.on("presence", cent.ApiError(108, "nope"))
    with pytest.raises(cent.NotAvailableError):
        a.presence(cent.PresenceRequest(channel="x"))
    with pytest.raises(cent.BroadcastFailedChannelsError):
        a.broadcast(cent.BroadcastRequest(channels=["bad:1"], data=1))
    fake.on("history", httpx2.Response(502))
    with pytest.raises(cent.HTTPError):
        a.history(cent.HistoryRequest(channel="x"))
    with pytest.raises(cent.InvalidRequestError):
        a.publish(cent.PublishRequest(channel="x", data=float("nan")))
    b = a.client.new_batch()
    b.publish(cent.PublishRequest(channel="x", data=1))
    b.presence(cent.PresenceRequest(channel="x"))
    with pytest.raises(cent.BatchFailedCommandsError):
        a.send(b)

    got = [(i.method, i.commands, i.failed, i.status_code, type(i.error).__name__ if i.error else None) for i in infos]
    assert got == [
        ("publish", 1, 0, 200, None),
        ("presence", 1, 1, 200, None),
        # A broadcast failing in some channels is answered: not counted.
        ("broadcast", 1, 0, 200, None),
        ("history", 1, 0, 502, "HTTPError"),
        # Encoding failed before reaching the network.
        ("publish", 1, 0, 0, "InvalidRequestError"),
        ("batch", 2, 1, 200, None),
    ]
    assert all(i.duration >= 0 for i in infos)


def test_on_request_transport_error_mode(new_api: Callable[..., Api], kind: str, fake: Fake) -> None:
    infos: list[cent.RequestInfo] = []
    a = new_api(on_request=infos.append)
    fake.on("publish", httpx2.Response(400, json={"code": 107, "message": "bad request"}))
    with pytest.raises(cent.BadRequestError):
        a.publish(cent.PublishRequest(channel="x", data=1))
    assert isinstance(infos[0].error, cent.BadRequestError)
    assert infos[0].failed == 0


# Shutdown.


def test_close(api: Api, fake: Fake) -> None:
    api.publish(cent.PublishRequest(channel="x", data=1))
    api.close()
    with pytest.raises(cent.ClosedError):
        api.publish(cent.PublishRequest(channel="x", data=1))
    api.close()  # again


def test_close_waits_for_calls_in_progress() -> None:
    import threading

    started, release = threading.Event(), threading.Event()

    def slow(request: httpx2.Request) -> httpx2.Response:
        started.set()
        release.wait(5)
        return httpx2.Response(200, json={"result": {}})

    c = cent.Client(ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(slow)))
    t = threading.Thread(target=lambda: c.publish(cent.PublishRequest(channel="x", data=1)))
    t.start()
    assert started.wait(5)
    with pytest.raises(cent.CentTimeoutError):
        c.close(timeout=0.05)
    release.set()
    c.close(timeout=5)
    t.join()


async def test_aclose_waits_for_calls_in_progress() -> None:
    release = asyncio.Event()

    async def slow(request: httpx2.Request) -> httpx2.Response:
        await release.wait()
        return httpx2.Response(200, json={"result": {}})

    c = cent.AsyncClient(ENDPOINT, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(slow)))
    task = asyncio.create_task(c.publish(cent.PublishRequest(channel="x", data=1)))
    await asyncio.sleep(0.01)
    with pytest.raises(cent.CentTimeoutError):
        await c.aclose(timeout=0.05)
    release.set()
    await c.aclose(timeout=5)
    await task


async def test_cancelled_call_is_not_retryable() -> None:
    async def hang(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(10)
        raise AssertionError

    c = cent.AsyncClient(ENDPOINT, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(hang)))
    task = asyncio.create_task(c.publish(cent.PublishRequest(channel="x", data=1)))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await c.aclose()


async def test_outer_asyncio_timeout_ends_a_call_sooner() -> None:
    async def hang(request: httpx2.Request) -> httpx2.Response:
        await asyncio.sleep(10)
        raise AssertionError

    c = cent.AsyncClient(ENDPOINT, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(hang)))
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.05):
            await c.publish(cent.PublishRequest(channel="x", data=1))
    assert time.monotonic() - start < 1


def test_context_managers(fake: Fake) -> None:
    with cent.Client(ENDPOINT, http_client=httpx2.Client(transport=httpx2.MockTransport(fake))) as c:
        c.publish(cent.PublishRequest(channel="x", data=1))
    with pytest.raises(cent.ClosedError):
        c.publish(cent.PublishRequest(channel="x", data=1))

    async def main() -> None:
        async with cent.AsyncClient(
            ENDPOINT, http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(fake))
        ) as c:
            await c.publish(cent.PublishRequest(channel="x", data=1))

    asyncio.run(main())


def test_retryable() -> None:
    assert not cent.retryable(None)
    assert not cent.retryable(cent.InvalidRequestError("x"))
    assert not cent.retryable(cent.InvalidConfigError("x"))
    assert not cent.retryable(cent.ClosedError("x"))
    assert not cent.retryable(cent.DecodeError("x"))
    assert not cent.retryable(asyncio.CancelledError())
    assert cent.retryable(TimeoutError())
    assert cent.retryable(cent.NetworkError("x"))
    import ssl

    try:
        try:
            raise ssl.SSLCertVerificationError("bad cert")
        except ssl.SSLCertVerificationError as e:
            raise httpx2.ConnectError("tls") from e
    except httpx2.ConnectError as e:
        net = cent.NetworkError("x")
        net.__cause__ = e
    assert not cent.retryable(net)


def test_broadcast_with_retry_retries_a_hung_attempt() -> None:
    """Without a timeout the call has no bound of its own: an attempt which
    hangs times out on its own - request_timeout - and is retried."""
    calls = [0]

    def handler(request: httpx2.Request) -> httpx2.Response:
        calls[0] += 1
        if calls[0] == 1:
            time.sleep(0.3)  # past request_timeout, as an attempt which hangs
            raise httpx2.ReadTimeout("hung", request=request)
        return httpx2.Response(200, json={"result": {"responses": [{"result": {"offset": 1}}]}})

    c = cent.Client(ENDPOINT, request_timeout=0.2, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    res = c.broadcast_with_retry(cent.BroadcastRequest(channels=["a"], data=1), on_attempt_error=lambda a: 0.0)
    assert calls[0] == 2
    assert res.attempts == 2
