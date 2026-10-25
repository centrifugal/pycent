"""The API client against a real Centrifugo."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

import cent
from cent import token
from tests.integration.conftest import ADDR, API_KEY, Stream

pytestmark = pytest.mark.integration


def test_publish_and_history(client: cent.Client, unique: Callable[[str], str]) -> None:
    ch = unique("")
    raw = cent.RawJSON('{"n":1.0,"big":18446744073709551617,"empty":{},"keys":{"0":"a"}}')
    res = client.publish(cent.PublishRequest(channel=ch, data=raw, tags={"k": "v"}))
    assert res.offset == 1
    assert res.epoch
    hist = client.history(cent.HistoryRequest(channel=ch, limit=10))
    (pub,) = hist.publications
    assert pub.tags == {"k": "v"}
    assert pub.data == {"n": 1.0, "big": 18446744073709551617, "empty": {}, "keys": {"0": "a"}}
    # Sent back unchanged, the payload is the same JSON value.
    client.publish(cent.PublishRequest(channel=ch, data=pub.data))
    again = client.history(cent.HistoryRequest(channel=ch, limit=10, reverse=True)).publications[0]
    assert again.data == pub.data
    assert isinstance(again.data["n"], float)
    client.history_remove(cent.HistoryRemoveRequest(channel=ch))
    assert client.history(cent.HistoryRequest(channel=ch, limit=10)).publications == []


def test_idempotency_key(client: cent.Client, unique: Callable[[str], str]) -> None:
    ch = unique("")
    first = client.publish(cent.PublishRequest(channel=ch, data=1, idempotency_key="k1"))
    second = client.publish(cent.PublishRequest(channel=ch, data=2, idempotency_key="k1"))
    assert first.offset == second.offset
    assert len(client.history(cent.HistoryRequest(channel=ch, limit=10)).publications) == 1


def test_broadcast(client: cent.Client, unique: Callable[[str], str]) -> None:
    a, b = unique("a-"), unique("b-")
    res = client.broadcast(cent.BroadcastRequest(channels=[a, b], data={"x": 1}))
    assert [c.result.offset for c in res.channels if c.result] == [1, 1]
    with pytest.raises(cent.BroadcastFailedChannelsError) as e:
        client.broadcast(cent.BroadcastRequest(channels=[a, "unknown:x"], data={"x": 2}))
    assert [f.channel for f in e.value.failed] == ["unknown:x"]
    assert isinstance(e.value.failed[0].error, cent.UnknownChannelError)
    assert e.value.result.channels[0].result is not None
    assert not cent.retryable(e.value)


def test_broadcast_with_retry(client: cent.Client, unique: Callable[[str], str]) -> None:
    a = unique("")
    res = client.broadcast_with_retry(cent.BroadcastRequest(channels=[a], data=1))
    assert res.idempotency_key.startswith("pycent-")
    # Retried later with the key, nothing is published again.
    client.broadcast(cent.BroadcastRequest(channels=[a], data=1, idempotency_key=res.idempotency_key))
    assert len(client.history(cent.HistoryRequest(channel=a, limit=10)).publications) == 1


def test_batch(client: cent.Client, unique: Callable[[str], str]) -> None:
    ch = unique("")
    b = client.new_batch()
    pub = b.publish(cent.PublishRequest(channel=ch, data=1))
    hist = b.history(cent.HistoryRequest(channel=ch, limit=1))
    bad = b.publish(cent.PublishRequest(channel="unknown:x", data=1))
    with pytest.raises(cent.BatchFailedCommandsError) as e:
        b.send()
    assert [f.index for f in e.value.failed] == [2]
    assert pub.result().offset == 1
    assert len(hist.result().publications) == 1
    with pytest.raises(cent.UnknownChannelError):
        bad.result()


def test_refused_request_is_not_retryable(client: cent.Client) -> None:
    with pytest.raises(cent.ApiError) as e:
        client.history(cent.HistoryRequest(channel="unknown:x"))
    assert not cent.retryable(e.value)


def test_pro_method(client: cent.Client) -> None:
    """A PRO method on Centrifugo OSS: a 404 which says so, and in a batch a 104
    which says so too. Against Centrifugo PRO it succeeds."""
    try:
        client.connections(cent.ConnectionsRequest(user="nobody"))
    except cent.HTTPError as e:
        err: cent.HTTPError | None = e
    else:
        err = None
    if err is None:
        return  # Centrifugo PRO
    assert err.status_code == 404
    assert "Centrifugo PRO method" in str(err)
    b = client.new_batch()
    conns = b.connections(cent.ConnectionsRequest(user="nobody"))
    with pytest.raises(cent.BatchFailedCommandsError):
        b.send()
    with pytest.raises(cent.NotFoundError, match="Centrifugo PRO method"):
        conns.result()


def test_info(client: cent.Client) -> None:
    info = client.info()
    assert info.nodes
    assert info.nodes[0].version


def test_map(client: cent.Client, unique: Callable[[str], str]) -> None:
    ch = "map:" + unique("")
    client.map_publish(cent.MapPublishRequest(channel=ch, key="k1", data={"v": 1}))
    client.map_publish(cent.MapPublishRequest(channel=ch, key="k2", data={"v": 2}))
    state = client.map_read_state(cent.MapReadStateRequest(channel=ch, limit=10))
    assert sorted(e.key for e in state.entries) == ["k1", "k2"]
    client.map_remove(cent.MapRemoveRequest(channel=ch, key="k1"))
    stats = client.map_stats(cent.MapStatsRequest(channel=ch))
    assert stats.num_keys == 1
    client.map_clear(cent.MapClearRequest(channel=ch))


def test_shared_poll_publish(client: cent.Client, unique: Callable[[str], str]) -> None:
    client.shared_poll_publish(
        cent.SharedPollPublishRequest(channel="poll:" + unique(""), key="k", version=1, data={"v": 1})
    )


def test_auto_batch_under_concurrency(unique: Callable[[str], str]) -> None:
    infos: list[cent.RequestInfo] = []
    lock = threading.Lock()

    def record(i: cent.RequestInfo) -> None:
        with lock:
            infos.append(i)

    c = cent.Client(ADDR, api_key=API_KEY, auto_batch=cent.AutoBatch(max_in_flight=2), on_request=record)
    ch = unique("")
    errors: list[Exception] = []

    def run(w: int) -> None:
        for n in range(20):
            try:
                c.publish(cent.PublishRequest(channel=f"{ch}-{w}", data={"n": n}))
            except Exception as e:
                errors.append(e)

    threads = [threading.Thread(target=run, args=(w,)) for w in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    c.close(timeout=10)
    assert errors == []
    assert any(i.auto_batch for i in infos)
    for w in range(16):
        hist = c_history(f"{ch}-{w}")
        assert [p.data["n"] for p in hist] == list(range(20))  # one after another: in order


def c_history(ch: str) -> list[cent.Publication]:
    with cent.Client(ADDR, api_key=API_KEY) as c:
        return c.history(cent.HistoryRequest(channel=ch, limit=100)).publications


def test_connection_with_tokens(
    client: cent.Client, unique: Callable[[str], str], stream: Callable[[dict[str, object]], Stream]
) -> None:
    """Tokens from cent.token connect a real client - HMAC, and Ed25519 verified
    by client.token.ed25519_public_key (the public key of the seed below, set
    in testdata/centrifugo.json) - and the server-side methods act on it."""
    exp = datetime.now(UTC) + timedelta(hours=1)
    keys = {
        "hmac": token.Key.hmac(b"client_secret"),
        "ed25519": token.Key.ed25519(ed25519.Ed25519PrivateKey.from_private_bytes(bytes([2] * 32))),
    }
    for name, key in keys.items():
        user = unique(f"{name}-")
        ch = user + "-news"
        tok = token.connection(
            key, token.ConnectionClaims(user=user, expires_at=exp, info={"name": "Alice"}, channels=[ch])
        )
        s = stream({"token": tok})
        msg = s.next()
        assert msg is not None
        assert "connect" in msg, msg
        assert ch in json.dumps(msg)
        pres = client.presence(cent.PresenceRequest(channel=ch))
        assert [(i.user, i.conn_info) for i in pres.presence.values()] == [(user, {"name": "Alice"})]
        assert client.presence_stats(cent.PresenceStatsRequest(channel=ch)).num_users == 1
        client.publish(cent.PublishRequest(channel=ch, data={"text": "hello"}))
        assert "hello" in json.dumps(s.next())
        other = ch + "-2"
        client.subscribe(cent.SubscribeRequest(user=user, channel=other))
        assert other in json.dumps(s.next())
        client.refresh(cent.RefreshRequest(user=user, expire_at=int(exp.timestamp())))
        client.disconnect(cent.DisconnectRequest(user=user))
        while s.next() is not None:
            pass

    # A token signed with another key is refused.
    bad = token.connection(
        token.Key.ed25519(ed25519.Ed25519PrivateKey.generate()), token.ConnectionClaims(user="u", expires_at=exp)
    )
    msg = stream({"token": bad}).next()
    assert msg is None or "disconnect" in msg


async def test_async_client(unique: Callable[[str], str]) -> None:
    async with cent.AsyncClient(ADDR, api_key=API_KEY, auto_batch=cent.AutoBatch(max_in_flight=2)) as c:
        ch = unique("")
        results = await asyncio.gather(
            *(c.publish(cent.PublishRequest(channel=f"{ch}-{i}", data=i)) for i in range(20))
        )
        assert all(r.offset == 1 for r in results)
        with pytest.raises(cent.BroadcastFailedChannelsError):
            await c.broadcast(cent.BroadcastRequest(channels=[ch, "unknown:x"], data=1))
        b = c.new_batch(parallel=True)
        p = b.publish(cent.PublishRequest(channel=ch, data=1))
        await b.send()
        assert p.result().offset >= 1
