"""Centrifugo PRO methods, API tokens and async consumers, against the Centrifugo
PRO of testdata/centrifugo-pro.compose.yml: user status, user blocking and
token revocation in Redis, devices in PostgreSQL, push notifications through
webpush in dry run.

The tests use Centrifugo PRO in sandbox mode, without a license key.
Centrifugo PRO is commercial software, under the Centrifugal Labs License
Agreement (https://centrifugal.dev/license), not under cent's MIT license.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

import cent
from cent import endpoints, token
from tests.integration.conftest import ADDR, API_KEY

pytestmark = pytest.mark.integration


def webpush_token() -> str:
    """A browser PushSubscription, as webpush devices are registered with."""
    pub = (
        ec.generate_private_key(ec.SECP256R1())
        .public_key()
        .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    )

    def e(b: bytes) -> str:
        return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

    return json.dumps(
        {
            "endpoint": "https://fcm.googleapis.com/fcm/send/" + e(pub[:8]),
            "keys": {"p256dh": e(pub), "auth": e(bytes(16))},
        }
    )


def test_user_status(pro: cent.Client, unique: Callable[[str], str]) -> None:
    user = unique("")
    pro.update_user_status(cent.UpdateUserStatusRequest(users=[user], state="away"))
    (st,) = pro.get_user_status(cent.GetUserStatusRequest(users=[user])).statuses
    assert (st.user, st.state) == (user, "away")
    assert st.active > 0
    pro.delete_user_status(cent.DeleteUserStatusRequest(users=[user]))
    (st,) = pro.get_user_status(cent.GetUserStatusRequest(users=[user])).statuses
    assert st.active == 0


def test_user_and_token_control(pro: cent.Client, unique: Callable[[str], str]) -> None:
    user = unique("")
    expire = int(time.time()) + 60
    pro.block_user(cent.BlockUserRequest(user=user, expire_at=expire))
    pro.unblock_user(cent.UnblockUserRequest(user=user))
    pro.revoke_token(cent.RevokeTokenRequest(uid=user + "-jti", expire_at=expire))
    pro.invalidate_user_tokens(
        cent.InvalidateUserTokensRequest(user=user, issued_before=int(time.time()), expire_at=expire)
    )


def test_devices_and_push(pro: cent.Client, unique: Callable[[str], str]) -> None:
    user = unique("")
    reg = pro.device_register(
        cent.DeviceRegisterRequest(
            provider="webpush",
            platform="web",
            token=webpush_token(),
            user=user,
            meta={"app": "pycent"},
            topics=["news"],
        )
    )
    assert reg.id
    by_user = cent.DeviceFilter(users=[user])
    lst = pro.device_list(
        cent.DeviceListRequest(filter=by_user, include_meta=True, include_topics=True, include_total_count=True)
    )
    assert lst.total_count == 1
    assert lst.items[0].id == reg.id
    assert lst.items[0].meta == {"app": "pycent"}
    assert "news" in lst.items[0].topics
    pro.device_topic_update(cent.DeviceTopicUpdateRequest(device_id=reg.id, op="add", topics=["sport"]))
    topics = pro.device_topic_list(
        cent.DeviceTopicListRequest(filter=cent.DeviceTopicFilter(device_ids=[reg.id]), include_total_count=True)
    )
    assert topics.total_count == 2
    pro.device_update(
        cent.DeviceUpdateRequest(ids=[reg.id], meta_update=cent.DeviceMetaUpdate(meta={"app": "updated"}))
    )
    assert pro.device_list(cent.DeviceListRequest(filter=by_user, include_meta=True)).items[0].meta == {
        "app": "updated"
    }
    pro.user_topic_update(cent.UserTopicUpdateRequest(user=user, op="add", topics=["alerts"]))
    ut = pro.user_topic_list(cent.UserTopicListRequest(filter=cent.UserTopicFilter(users=[user])))
    assert [i.topic for i in ut.items] == ["alerts"]
    push = pro.send_push_notification(
        cent.SendPushNotificationRequest(
            recipient=cent.PushRecipient(filter=by_user),
            notification=cent.PushNotification(webpush=cent.WebPushPushNotification(payload={"title": "hi"})),
            send_at=int(time.time()) + 3600,
        )
    )
    assert push.uid
    pro.cancel_push(cent.CancelPushRequest(uid=push.uid))
    # Push status needs push analytics in ClickHouse; without it, the method
    # is not available.
    with contextlib.suppress(cent.NotAvailableError):
        pro.update_push_status(
            cent.UpdatePushStatusRequest(analytics_uid=push.uid, status="delivered", device_id=reg.id)
        )
    pro.device_remove(cent.DeviceRemoveRequest(ids=[reg.id]))
    assert pro.device_list(cent.DeviceListRequest(filter=by_user)).items == []


def test_pro_batch(pro: cent.Client, unique: Callable[[str], str]) -> None:
    user = unique("")
    b = pro.new_batch()
    b.update_user_status(cent.UpdateUserStatusRequest(users=[user], state="busy"))
    status = b.get_user_status(cent.GetUserStatusRequest(users=[user]))
    reg = b.device_register(
        cent.DeviceRegisterRequest(provider="webpush", platform="web", token=webpush_token(), user=user)
    )
    conns = b.connections(cent.ConnectionsRequest(user=user))
    b.send()
    assert status.result().statuses[0].state == "busy"
    r = reg.result()
    assert r.id
    assert conns.result().connections == {}

    # max_in_flight 1 queues every call made while another is in flight.
    auto = cent.Client(ADDR, api_key=API_KEY, auto_batch=cent.AutoBatch(max_in_flight=1))
    errors: list[Exception] = []

    def run() -> None:
        try:
            res = auto.device_list(cent.DeviceListRequest(filter=cent.DeviceFilter(users=[user])))
            assert [i.id for i in res.items] == [r.id]
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=run) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    auto.close()
    assert errors == []
    pro.device_remove(cent.DeviceRemoveRequest(ids=[r.id]))


def test_api_tokens(pro: cent.Client, unique: Callable[[str], str], serve: Callable[[int, Any], None]) -> None:
    """Tokens from token.APITokens authenticate API calls to Centrifugo PRO,
    which verifies them with the keys served here, at the endpoint of
    testdata/centrifugo-pro.compose.yml: port 3101 of the host. Tokens without
    the audience and scope it requires are refused, as are tokens signed with
    a key not published."""

    # The same keys on every run, from fixed seeds: Centrifugo caches keys by
    # ID, so a new key under a known ID would be refused.
    def key(kid: str, seed: int) -> token.Key:
        return token.Key.ed25519(ed25519.Ed25519PrivateKey.from_private_bytes(bytes([seed] * 32))).with_key_id(kid)

    api_key = key("gocent-api-test", 1)
    jwks = endpoints.JWKS(api_key)

    def app(environ: dict[str, Any], start_response: Any) -> Any:
        if environ.get("PATH_INFO") != "/api_jwks":
            start_response("404 Not Found", [])
            return [b""]
        return jwks.wsgi(environ, start_response)

    serve(int(os.environ.get("PYCENT_TEST_API_JWKS_PORT", "3101")), app)

    def publish(token_func: Callable[[], str]) -> None:
        with cent.Client(ADDR, bearer_token_func=token_func) as c:
            c.publish(cent.PublishRequest(channel=unique(""), data={}))

    tokens = token.APITokens(key=api_key, claims=token.APIClaims(audience="centrifugo-api", scope=["centrifugo:api"]))
    publish(tokens.token)

    exp = datetime.now(UTC) + timedelta(minutes=1)
    for claims in (
        token.APIClaims(audience="centrifugo-api", expires_at=exp),
        token.APIClaims(scope=["centrifugo:api"], expires_at=exp),
    ):
        tok = token.api(api_key, claims)
        with pytest.raises(cent.UnauthorizedError):
            publish(lambda tok=tok: tok)  # type: ignore[misc]

    # A connection token signed with a published key: no audience or scope.
    conn = token.connection(api_key, token.ConnectionClaims(user="42", expires_at=exp))
    with pytest.raises(cent.UnauthorizedError):
        publish(lambda: conn)

    unpublished = token.APITokens(key=key("gocent-unpublished", 2), claims=token.APIClaims(audience="centrifugo-api"))
    with pytest.raises(cent.UnauthorizedError):
        publish(unpublished.token)


def redis_xadd(addr: str, stream: str, *fields: str) -> None:
    host, port = addr.rsplit(":", 1)
    args = ["XADD", stream, "*", *fields]
    cmd = f"*{len(args)}\r\n" + "".join(f"${len(a.encode())}\r\n{a}\r\n" for a in args)
    with socket.create_connection((host, int(port)), timeout=5) as s:
        s.sendall(cmd.encode())
        reply = s.recv(1024)
    assert reply.startswith(b"$"), reply


def test_command_consumed(pro: cent.Client, unique: Callable[[str], str]) -> None:
    """Commands from cent.new_command, written to a Redis stream, are run by
    Centrifugo's async consumer: apart, as method and payload, and whole."""
    addr = os.environ.get("PYCENT_TEST_REDIS", "localhost:46379")
    ch = unique("")
    apart = cent.new_command(cent.PublishRequest(channel=ch, data={"n": 1}))
    redis_xadd(addr, "pycent_commands", "method", apart.method, "payload", apart.payload)
    whole = cent.new_command(cent.PublishRequest(channel=ch, data={"n": 2}))
    redis_xadd(addr, "pycent_commands", "payload", whole.to_json())
    deadline = time.monotonic() + 15
    while True:
        pubs = pro.history(cent.HistoryRequest(channel=ch, limit=10)).publications
        if len(pubs) == 2:
            assert [p.data for p in pubs] == [{"n": 1}, {"n": 2}]
            return
        assert time.monotonic() < deadline, f"{len(pubs)} of 2 commands consumed after 15s"
        time.sleep(0.1)
