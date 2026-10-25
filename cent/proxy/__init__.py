"""The application side of Centrifugo's HTTP proxy: the requests Centrifugo
sends to the backend when a client connects, subscribes, publishes or calls an
RPC, the results the backend answers with, and a handler for each proxy type
which decodes the request, calls a function and encodes its answer.

>>> def connect(request: cent.HTTPRequest, req: proxy.ConnectRequest) -> proxy.ConnectResult:
...     user = session_user(request.headers.get("cookie"))  # passed on with http_headers
...     if user is None:
...         raise proxy.Disconnect(4501, "unauthorized")
...     return proxy.ConnectResult(user=user)
>>> app.mount("/centrifugo/connect", proxy.ConnectHandler(connect).asgi)

and in Centrifugo's configuration:

    "client": {"proxy": {"connect": {"enabled": true,
        "endpoint": "http://backend:3000/centrifugo/connect", "http_headers": ["Cookie"]}}}

See https://centrifugal.dev/docs/server/proxy.

Answering: a function returns a result to accept the request, or raises:

- ProxyError rejects the request with that error, which the client receives:
  use codes in [400, 1999]. The connect, subscribe, publish, RPC, map publish
  and map remove proxies pass it to the client; the shared poll refresh and
  channel state proxies take it as a failure.
- Disconnect closes the client's connection with that code: use codes in
  [4000, 4999] - [4500, 4999] to tell the client not to reconnect. Only the
  proxies which pass a ProxyError to the client honour it.
- Any other exception, or one a proxy cannot carry, fails the request with
  HTTP status 500, and is passed to on_error for logging. Centrifugo then
  answers the client with its temporary internal error; for refresh and sub
  refresh it keeps the connection or subscription for another minute and
  asks again.

A ProxyError or Disconnect raised from another exception (``raise ... from``)
counts too. The refresh and sub refresh proxies end a connection or
subscription through their result's expired, not an exception. A handler
answers with exactly one of result, error and disconnect: Centrifugo would take
a response with none as accepting the request as the client sent it.

Payloads - data, info, meta - arrive as the values they decode to, and a
result takes them back as they are, or as cent.RawJSON. A proxy with
binary_encoding enabled sends them base64-encoded in the b64 fields, with
encoding "binary"; a result may answer with either field.

Security: Centrifugo trusts what a proxy endpoint answers, and the endpoint
trusts what Centrifugo sends - a SubscribeRequest's user is the user
Centrifugo authenticated. Anyone else able to reach the endpoint could claim
any user. Keep proxy endpoints reachable by Centrifugo only: on an internal
network, or behind a check of a secret Centrifugo sends as a static header.

Centrifugo's GRPC proxy is not covered: generate GRPC code from proxy.proto
for it.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

from cent import _wire as _w
from cent._errors import DecodeError, InvalidRequestError
from cent._http import Handler, HTTPRequest, HTTPResponse, allow
from cent.proxy import _types
from cent.proxy._types import *  # noqa: F403 - the generated requests and results
from cent.proxy._types import (
    ConnectRequest,
    ConnectResult,
    MapPublishRequest,
    MapPublishResult,
    MapRemoveRequest,
    MapRemoveResult,
    NotifyCacheEmptyRequest,
    NotifyCacheEmptyResult,
    NotifyChannelStateRequest,
    NotifyChannelStateResult,
    PublishRequest,
    PublishResult,
    RefreshRequest,
    RefreshResult,
    RPCRequest,
    RPCResult,
    SharedPollRefreshRequest,
    SharedPollRefreshResult,
    SubRefreshRequest,
    SubRefreshResult,
    SubscribeRequest,
    SubscribeResult,
)

_Req = TypeVar("_Req")
_Res = TypeVar("_Res")

OnError = Callable[[HTTPRequest, Exception], None]

DEFAULT_MAX_BODY = 16 << 20
"""The default bound of a request's body, 16 MiB: far above what Centrifugo's
own limits on client messages let through, it only stops a request which is
not Centrifugo's from taking the memory it likes."""


class ProxyError(Exception):
    """Raised by a proxy function to reject the client's request with this error:
    code in [400, 1999], which Centrifugo leaves to applications. temporary
    tells the client that retrying may succeed."""

    def __init__(self, code: int, message: str = "", temporary: bool = False) -> None:
        super().__init__(code, message)
        self.code = code
        self.message = message
        self.temporary = temporary

    def __str__(self) -> str:
        return f"{self.message} (code {self.code})"


class Disconnect(Exception):
    """Raised by a proxy function to close the client's connection: code in
    [4000, 4999] - [4000, 4499] tells the client to reconnect, [4500, 4999] not
    to. reason is a short description, at most 32 bytes."""

    def __init__(self, code: int, reason: str = "") -> None:
        super().__init__(code, reason)
        self.code = code
        self.reason = reason

    def __str__(self) -> str:
        return f"disconnect: {self.reason} (code {self.code})"


def _find(err: BaseException | None, cls: type[BaseException]) -> Any:
    """err or its cause, when it is a cls."""
    while err is not None:
        if isinstance(err, cls):
            return err
        err = err.__cause__
    return None


# What a proxy type's response can carry, besides a result.
_RESULT_ONLY, _ERROR, _ERROR_DISCONNECT = 0, 1, 2


class _ProxyHandler(Handler, Generic[_Req, _Res]):
    _name: str
    _request: type[Any]
    _result: type[Any]
    _answers: int

    def __init__(
        self,
        func: Callable[[HTTPRequest, _Req], _Res | Awaitable[_Res]],
        *,
        on_error: OnError | None = None,
        max_body: int = DEFAULT_MAX_BODY,
    ) -> None:
        if func is None:
            raise TypeError(f"{type(self).__name__} takes the function answering the {self._name} proxy")
        if isinstance(max_body, bool) or not isinstance(max_body, int) or max_body <= 0:
            raise ValueError("max_body must be a positive number of bytes")
        super().__init__(func, on_error)
        self.max_body = max_body

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        if req.method != "POST":
            return allow("POST")
        try:
            decoded = self._request._from_wire(json.loads(body))
        except (ValueError, RecursionError, DecodeError) as e:
            return self._fail(req, 400, ValueError(f"proxy: malformed {self._name} request: {e}"))
        return (decoded,)

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        if error is None:
            if not isinstance(out, self._result):
                got = type(out).__name__
                return self._fail(
                    req, 500, TypeError(f"proxy: the {self._name} function returned {got}, not {self._result.__name__}")
                )
            wire: dict[str, Any] = {"result": out._to_wire()}
        else:
            d, e = _find(error, Disconnect), _find(error, ProxyError)
            if d is not None and self._answers == _ERROR_DISCONNECT:
                wire = {"disconnect": {"code": d.code, "reason": d.reason}}
            elif e is not None and self._answers != _RESULT_ONLY:
                pe: dict[str, Any] = {"code": e.code, "message": e.message}
                if e.temporary:
                    pe["temporary"] = True
                wire = {"error": pe}
            elif d is not None or e is not None:
                # Centrifugo would ignore it in this proxy's response.
                return self._fail(
                    req,
                    500,
                    ValueError(f"proxy: the {self._name} proxy cannot answer with {error!r}: failing the request"),
                )
            else:
                return self._fail(req, 500, error)
        try:
            body = _w.encode(wire, self._name)
        except InvalidRequestError as e:
            # A payload which is not JSON, say: Centrifugo could not use the
            # response.
            return self._fail(req, 500, e)
        return HTTPResponse(200, [("Content-Type", "application/json")], body)


class ConnectHandler(_ProxyHandler[ConnectRequest, ConnectResult]):
    """The connect proxy: the function authenticates a connecting client and
    returns its user and initial state. ProxyError rejects the connection;
    Disconnect closes it with that code."""

    _name, _request, _result, _answers = "connect", ConnectRequest, ConnectResult, _ERROR_DISCONNECT


class RefreshHandler(_ProxyHandler[RefreshRequest, RefreshResult]):
    """The refresh proxy: the function decides whether a connection about to
    expire lives on, and until when. To end it, return a result with expired
    set. Any exception fails the request, and Centrifugo keeps the connection
    for another minute before asking again."""

    _name, _request, _result, _answers = "refresh", RefreshRequest, RefreshResult, _RESULT_ONLY


class SubscribeHandler(_ProxyHandler[SubscribeRequest, SubscribeResult]):
    """The subscribe proxy: the function decides whether a client may subscribe
    to a channel. ProxyError rejects the subscription; Disconnect closes the
    connection."""

    _name, _request, _result, _answers = "subscribe", SubscribeRequest, SubscribeResult, _ERROR_DISCONNECT


class PublishHandler(_ProxyHandler[PublishRequest, PublishResult]):
    """The publish proxy: the function decides whether a client may publish into
    a channel, and may change the publication. ProxyError rejects it;
    Disconnect closes the connection."""

    _name, _request, _result, _answers = "publish", PublishRequest, PublishResult, _ERROR_DISCONNECT


class RPCHandler(_ProxyHandler[RPCRequest, RPCResult]):
    """The RPC proxy: the function answers a client's RPC call. ProxyError fails
    the call; Disconnect closes the connection."""

    _name, _request, _result, _answers = "rpc", RPCRequest, RPCResult, _ERROR_DISCONNECT


class SubRefreshHandler(_ProxyHandler[SubRefreshRequest, SubRefreshResult]):
    """The sub refresh proxy: the function decides whether a subscription about
    to expire lives on, and until when. To end it, return a result with
    expired set. Any exception fails the request, and Centrifugo keeps the
    subscription for another minute before asking again."""

    _name, _request, _result, _answers = "sub refresh", SubRefreshRequest, SubRefreshResult, _RESULT_ONLY


class MapPublishHandler(_ProxyHandler[MapPublishRequest, MapPublishResult]):
    """The map publish proxy: the function decides whether a client may publish
    a key into a map channel, and may change the publication."""

    _name, _request, _result, _answers = "map publish", MapPublishRequest, MapPublishResult, _ERROR_DISCONNECT


class MapRemoveHandler(_ProxyHandler[MapRemoveRequest, MapRemoveResult]):
    """The map remove proxy: the function decides whether a client may remove a
    key from a map channel."""

    _name, _request, _result, _answers = "map remove", MapRemoveRequest, MapRemoveResult, _ERROR_DISCONNECT


class SharedPollRefreshHandler(_ProxyHandler[SharedPollRefreshRequest, SharedPollRefreshResult]):
    """The shared poll refresh proxy: the function returns the current data of
    the items tracked in a shared poll channel. ProxyError, or any other
    exception, fails the refresh: Centrifugo tries again at the next
    interval."""

    _name, _request, _result, _answers = (
        "shared poll refresh",
        SharedPollRefreshRequest,
        SharedPollRefreshResult,
        _ERROR,
    )


class NotifyCacheEmptyHandler(_ProxyHandler[NotifyCacheEmptyRequest, NotifyCacheEmptyResult]):
    """The cache empty proxy of Centrifugo PRO: the function learns that a client
    subscribed to a channel in cache recovery mode with nothing to recover, and
    may publish the current state - then it returns a result with populated
    set, for Centrifugo to recover once more. Any exception fails the request,
    and the client which subscribed is disconnected to reconnect."""

    _name, _request, _result, _answers = "cache empty", NotifyCacheEmptyRequest, NotifyCacheEmptyResult, _RESULT_ONLY


class NotifyChannelStateHandler(_ProxyHandler[NotifyChannelStateRequest, NotifyChannelStateResult]):
    """The channel state proxy of Centrifugo PRO, in preview: the function
    receives channels becoming occupied or vacated. ProxyError, or any other
    exception, fails the request."""

    _name, _request, _result, _answers = (
        "channel state",
        NotifyChannelStateRequest,
        NotifyChannelStateResult,
        _ERROR,
    )


__all__ = [
    "DEFAULT_MAX_BODY",
    "ConnectHandler",
    "Disconnect",
    "MapPublishHandler",
    "MapRemoveHandler",
    "NotifyCacheEmptyHandler",
    "NotifyChannelStateHandler",
    "ProxyError",
    "PublishHandler",
    "RPCHandler",
    "RefreshHandler",
    "SharedPollRefreshHandler",
    "SubRefreshHandler",
    "SubscribeHandler",
]
__all__ += _types.__all__
