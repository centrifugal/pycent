"""The HTTP endpoints client SDKs call: for connection and subscription tokens
- what their getToken callbacks fetch - and for shared poll signatures, plus
the JSON Web Key Set Centrifugo fetches.

>>> def issue(request: cent.HTTPRequest) -> str:
...     user = session_user(request.headers.get("cookie"))
...     if user is None:
...         raise endpoints.Unauthorized
...     return token.connection(key, token.ConnectionClaims(
...         user=user, expires_at=datetime.now(UTC) + timedelta(minutes=15)))
>>> conn = endpoints.ConnectionToken(issue)
>>> app.mount("/centrifugo/connection_token", conn.asgi)   # FastAPI, Starlette

An endpoint answers a JSON object, never cached; Unauthorized - also as the
cause of another exception - with 403, on which client SDKs stop asking, and
disconnect or unsubscribe; any other exception with 500, which they retry.
A malformed request gets 400, a wrong method 405. on_error, when set, is told
of every 500 and 400, with the exception; it must not raise.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from cent import token
from cent._http import Handler, HTTPRequest, HTTPResponse, allow, json_response

__all__ = ["JWKS", "ConnectionToken", "SharedPollSignature", "SubscriptionToken", "Unauthorized"]

OnError = Callable[[HTTPRequest, Exception], None]


class Unauthorized(Exception):
    """Raised by the function of an endpoint when the user may not have a token
    or signature: answered with 403, on which client SDKs stop asking. It is
    the endpoints' own, named after client SDKs' UnauthorizedError - not the
    API client's cent.UnauthorizedError, which means Centrifugo refused the
    SDK's credentials."""


def _unauthorized(err: BaseException) -> bool:
    while err is not None:
        if isinstance(err, Unauthorized):
            return True
        err = err.__cause__  # type: ignore[assignment]
    return False


class _Endpoint(Handler):
    def _answer(self, req: HTTPRequest, body: Any, error: Exception | None) -> HTTPResponse:
        if error is not None:
            if _unauthorized(error):
                return HTTPResponse(403, [("Content-Type", "text/plain; charset=utf-8")], b"Forbidden")
            return self._fail(req, 500, error)
        return json_response(json.dumps(body, separators=(",", ":")).encode())

    def _json(self, req: HTTPRequest, body: bytes) -> dict[str, Any] | HTTPResponse:
        try:
            d = json.loads(body)
        except (ValueError, RecursionError) as e:
            return self._fail(req, 400, ValueError(f"malformed request: {e}"))
        if not isinstance(d, dict):
            return self._fail(req, 400, ValueError("malformed request: not a JSON object"))
        return d


def _token(out: Any) -> str:
    if not isinstance(out, str) or not out:
        raise TypeError(f"the function returned {type(out).__name__}, not a token")
    return out


class ConnectionToken(_Endpoint):
    """The endpoint a client's getToken callback calls: issue(request) returns
    the connection token of the request's user - from token.connection, say -
    or raises Unauthorized. It takes GET and POST, the body ignored. issue may
    be a coroutine function, served by ahandle and asgi."""

    def __init__(
        self, issue: Callable[[HTTPRequest], str | Awaitable[str]], *, on_error: OnError | None = None
    ) -> None:
        if issue is None:
            raise TypeError("ConnectionToken takes the function issuing tokens")
        super().__init__(issue, on_error)

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        if req.method not in ("GET", "POST"):
            return allow("GET, POST")
        return ()

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        if error is None:
            try:
                return self._answer(req, {"token": _token(out)}, None)
            except TypeError as e:
                error = e
        return self._answer(req, None, error)


class SubscriptionToken(_Endpoint):
    """The endpoint a subscription's getToken callback calls: issue(request,
    channel) returns the token of the request's user for channel - from
    token.subscription, say - or raises Unauthorized when the user may not
    subscribe. The channel comes from a POST's JSON body, {"channel": ...},
    or from a GET's channel query parameter; it is required."""

    def __init__(
        self, issue: Callable[[HTTPRequest, str], str | Awaitable[str]], *, on_error: OnError | None = None
    ) -> None:
        if issue is None:
            raise TypeError("SubscriptionToken takes the function issuing tokens")
        super().__init__(issue, on_error)

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        if req.method == "GET":
            channel = req.query.get("channel", "")
        elif req.method == "POST":
            d = self._json(req, body)
            if isinstance(d, HTTPResponse):
                return d
            channel = d.get("channel", "")
            if not isinstance(channel, str):
                return self._fail(req, 400, ValueError("malformed request: channel is not a string"))
        else:
            return allow("GET, POST")
        if not channel:
            return self._fail(req, 400, ValueError("subscription token request without a channel"))
        return (channel,)

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        if error is None:
            try:
                return self._answer(req, {"token": _token(out)}, None)
            except TypeError as e:
                error = e
        return self._answer(req, None, error)


class SharedPollSignature(_Endpoint):
    """The endpoint a shared poll subscription's getSignature callback calls: a
    POST of {"channel": ..., "keys": [...]}, answered {"signature": ...,
    "keys": [...]}.

    sign(request, channel, keys) decides which of keys the user may track in
    channel, signs them - with sharedpoll.sign, say - and returns them, in the
    order signed, with the signature: ``(allowed, signature)``. The keys it
    leaves out are revoked: the client stops tracking them. To end the
    subscription instead, it raises Unauthorized. It may return only keys it
    was asked for: a signature covering another would be refused, and such a
    key fails the request with 500.
    """

    def __init__(
        self,
        sign: Callable[[HTTPRequest, str, list[str]], tuple[Sequence[str], str] | Awaitable[tuple[Sequence[str], str]]],
        *,
        on_error: OnError | None = None,
    ) -> None:
        if sign is None:
            raise TypeError("SharedPollSignature takes the function signing keys")
        super().__init__(sign, on_error)

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        if req.method != "POST":
            return allow("POST")
        d = self._json(req, body)
        if isinstance(d, HTTPResponse):
            return d
        channel, keys = d.get("channel", ""), d.get("keys") or []
        if not isinstance(channel, str) or not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
            return self._fail(req, 400, ValueError("malformed request: channel and keys must be strings"))
        if not channel:
            return self._fail(req, 400, ValueError("signature request without a channel"))
        return (channel, keys)

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        if error is None:
            try:
                allowed, signature = out
                allowed = list(allowed)
                if not isinstance(signature, str) or not all(isinstance(k, str) for k in allowed):
                    raise TypeError("the function must return (keys, signature)")
                asked = set(args[1])
                for k in allowed:
                    if k not in asked:
                        raise ValueError(f"signed key {k!r} the client did not ask for")
            except (TypeError, ValueError) as e:
                return self._answer(req, None, e)
            # The SDK reads the keys as an array, empty included.
            return self._answer(req, {"signature": signature, "keys": allowed}, None)
        return self._answer(req, None, error)


class JWKS(Handler):
    """Serves the JSON Web Key Set of keys - see token.jwks - at the URL
    configured as Centrifugo's client.token.jwks_public_endpoint. It answers
    GET and HEAD, cacheable for five minutes. A set token.jwks refuses fails
    here, when the endpoint is built."""

    def __init__(self, *keys: token.Key) -> None:
        super().__init__(None, None)
        self._body = token.jwks(*keys).encode()

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        if req.method not in ("GET", "HEAD"):
            return allow("GET, HEAD")
        return HTTPResponse(
            200,
            [("Content-Type", "application/json"), ("Cache-Control", "public, max-age=300")],
            self._body if req.method == "GET" else b"",
        )

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        raise NotImplementedError  # _begin always answers
