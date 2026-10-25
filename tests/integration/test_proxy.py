"""The proxy handlers, called by a real Centrifugo: testdata/centrifugo.json
points its connect and refresh proxies at port 3100 of the host, which it
reaches as host.docker.internal, or PYCENT_TEST_PROXY_PORT."""

from __future__ import annotations

import json
import os
import queue
import time
from collections.abc import Callable
from typing import Any

import pytest

import cent
from cent import proxy
from tests.integration.conftest import Stream

pytestmark = pytest.mark.integration

PORT = int(os.environ.get("PYCENT_TEST_PROXY_PORT", "3100"))


class Router:
    """Routes a request to a handler's WSGI app by path."""

    def __init__(self, routes: dict[str, Any]) -> None:
        self.routes = routes

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        app = self.routes.get(environ.get("PATH_INFO", ""))
        if app is None:
            start_response("404 Not Found", [])
            return [b""]
        return app(environ, start_response)


def test_connect_and_refresh(
    client: cent.Client,
    unique: Callable[[str], str],
    serve: Callable[[int, Any], None],
    stream: Callable[[dict[str, Any]], Stream],
) -> None:
    user = unique("proxy-")
    ch = user + "-news"
    connects: queue.Queue[proxy.ConnectRequest] = queue.Queue()
    refreshes: queue.Queue[proxy.RefreshRequest] = queue.Queue()
    errors: list[Exception] = []

    def connect(request: cent.HTTPRequest, req: proxy.ConnectRequest) -> proxy.ConnectResult:
        connects.put(req)
        if not req.data.get("allow"):
            raise proxy.Disconnect(4501, "unauthorized")
        return proxy.ConnectResult(
            user=user,
            expire_at=int(time.time()) + 2,
            info={"name": "Alice"},
            data={"welcome": True},
            channels=[ch],
        )

    def refresh(request: cent.HTTPRequest, req: proxy.RefreshRequest) -> proxy.RefreshResult:
        refreshes.put(req)
        return proxy.RefreshResult(expired=True)

    serve(
        PORT,
        Router(
            {
                "/connect": proxy.ConnectHandler(connect, on_error=lambda r, e: errors.append(e)).wsgi,
                "/refresh": proxy.RefreshHandler(refresh, on_error=lambda r, e: errors.append(e)).wsgi,
            }
        ),
    )

    # Refused: the connection is closed with the disconnect's code.
    refused = stream({"data": {"allow": False}})
    req = connects.get(timeout=10)
    assert (req.transport, req.protocol, req.encoding) == ("uni_http_stream", "json", "json")
    assert req.client
    msg = refused.next()
    assert msg is not None
    assert msg.get("disconnect", {}).get("code") == 4501

    # Accepted: the result's data and server-side channel reach the client,
    # and so does a publication into that channel.
    s = stream({"data": {"allow": True}})
    connects.get(timeout=10)
    reply = s.next()
    assert reply is not None
    assert reply["connect"]["data"] == {"welcome": True}
    assert ch in reply["connect"]["subs"]
    client.publish(cent.PublishRequest(channel=ch, data={"text": "hello"}))
    assert "hello" in json.dumps(s.next())
    pres = client.presence(cent.PresenceRequest(channel=ch))
    assert [(i.user, i.conn_info) for i in pres.presence.values()] == [(user, {"name": "Alice"})]

    # It expires: Centrifugo asks the refresh proxy, which ends it.
    ref = refreshes.get(timeout=30)
    assert ref.user == user
    assert ref.client == reply["connect"]["client"]
    while s.next() is not None:
        pass
    assert errors == []
