"""The HTTP handlers' framework-free core, and its ASGI and WSGI adapters.

Each handler - a token or signature endpoint, the JWKS endpoint, a proxy
handler - turns a request into a response with handle (blocking) or ahandle
(async). Its asgi and wsgi attributes serve it as an ASGI or WSGI app, which
every Python web framework can mount; any other server calls the core.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl

__all__ = ["HTTPRequest", "HTTPResponse", "Handler"]


class _Headers(Mapping[str, str]):
    """Request headers, looked up case-insensitively."""

    __slots__ = ("_d",)

    def __init__(self, items: Iterable[tuple[str, str]]) -> None:
        self._d: dict[str, str] = {}
        for k, v in items:
            lk = k.lower()
            self._d[lk] = f"{self._d[lk]}, {v}" if lk in self._d else v

    def __getitem__(self, key: str) -> str:
        return self._d[key.lower()]

    def __iter__(self) -> Any:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __repr__(self) -> str:
        return f"Headers({self._d!r})"


@dataclass(frozen=True, slots=True)
class HTTPRequest:
    """A request to a handler, as the application's function receives it."""

    method: str
    """The HTTP method, upper case."""

    headers: Mapping[str, str]
    """The headers, looked up case-insensitively: those Centrifugo passes on
    from the client's connection to a proxy, the client SDK's to an endpoint."""

    query: Mapping[str, str] = field(default_factory=dict)
    """The query parameters, the first value of each."""

    path: str = ""
    """The path, as the server saw it."""

    raw: Any = None
    """The server's own form of the request: the ASGI scope, the WSGI environ,
    or what was given to handle - for what the core does not carry, such as
    the client's address."""


@dataclass(slots=True)
class HTTPResponse:
    """A handler's answer."""

    status: int
    headers: list[tuple[str, str]]
    body: bytes


def text(status: int, message: str, extra: list[tuple[str, str]] | None = None) -> HTTPResponse:
    return HTTPResponse(status, [("Content-Type", "text/plain; charset=utf-8"), *(extra or [])], message.encode())


_REASONS = {400: "Bad Request", 403: "Forbidden", 405: "Method Not Allowed", 500: "Internal Server Error"}


def status_text(status: int) -> HTTPResponse:
    return text(status, _REASONS.get(status, str(status)))


def allow(methods: str) -> HTTPResponse:
    return text(405, f"only {methods} allowed", [("Allow", methods)])


class Handler:
    """The base of every handler: subclasses implement _begin and _end."""

    max_body: int = 1 << 20

    def __init__(
        self, func: Callable[..., Any] | None, on_error: Callable[[HTTPRequest, Exception], None] | None
    ) -> None:
        if func is not None and not callable(func):
            raise TypeError(f"{type(self).__name__} takes a function")
        if on_error is not None and not callable(on_error):
            raise TypeError("on_error must be callable")
        self._func = func
        self._on_error = on_error
        self._is_async = func is not None and (
            inspect.iscoroutinefunction(func) or inspect.iscoroutinefunction(getattr(func, "__call__", None))  # noqa: B004
        )

    # What subclasses implement.

    def _begin(self, req: HTTPRequest, body: bytes) -> HTTPResponse | tuple[Any, ...]:
        """The arguments of the function after the request, or the response
        when the request is answered without calling it."""
        raise NotImplementedError

    def _end(self, req: HTTPRequest, args: tuple[Any, ...], out: Any, error: Exception | None) -> HTTPResponse:
        """The response to what the function returned or raised."""
        raise NotImplementedError

    def _fail(self, req: HTTPRequest, status: int, err: Exception) -> HTTPResponse:
        """status, after telling on_error of err."""
        if self._on_error is not None:
            self._on_error(req, err)
        return status_text(status)

    # The core.

    def handle(
        self,
        method: str,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        body: bytes = b"",
        *,
        query: Mapping[str, str] | None = None,
        path: str = "",
        raw: Any = None,
    ) -> HTTPResponse:
        """Answers a request with a blocking function. raw is passed on to the
        function as HTTPRequest.raw: the server's own request object."""
        req = _request(method, headers, query, path, raw)
        if len(body) > self.max_body:
            return self._fail(req, 400, ValueError(f"request body over {self.max_body} bytes"))
        begun = self._begin(req, body)
        if isinstance(begun, HTTPResponse):
            return begun
        if self._is_async:
            raise TypeError(f"{type(self).__name__}: an async function needs ahandle or asgi")
        assert self._func is not None  # noqa: S101 - _begin answers itself without one
        try:
            out = self._func(req, *begun)
        except Exception as e:
            return self._end(req, begun, None, e)
        if inspect.isawaitable(out):
            close = getattr(out, "close", None)
            if close is not None:
                close()
            raise TypeError(f"{type(self).__name__}: the function returned an awaitable: use ahandle or asgi")
        return self._end(req, begun, out, None)

    async def ahandle(
        self,
        method: str,
        headers: Mapping[str, str] | Iterable[tuple[str, str]] | None = None,
        body: bytes = b"",
        *,
        query: Mapping[str, str] | None = None,
        path: str = "",
        raw: Any = None,
    ) -> HTTPResponse:
        """Answers a request, awaiting an async function. A blocking one runs in
        a thread, so that it does not block the event loop."""
        req = _request(method, headers, query, path, raw)
        if len(body) > self.max_body:
            return self._fail(req, 400, ValueError(f"request body over {self.max_body} bytes"))
        begun = self._begin(req, body)
        if isinstance(begun, HTTPResponse):
            return begun
        func = self._func
        assert func is not None  # noqa: S101 - _begin answers itself without one
        try:
            if self._is_async:
                out = await func(req, *begun)
            else:
                out = await asyncio.to_thread(func, req, *begun)
                if inspect.isawaitable(out):
                    out = await out
        except Exception as e:
            return self._end(req, begun, None, e)
        return self._end(req, begun, out, None)

    # The adapters.

    async def asgi(self, scope: dict[str, Any], receive: Callable[[], Awaitable[dict[str, Any]]], send: Any) -> None:
        """The handler as an ASGI app: app.mount("/centrifugo/connect", handler.asgi)
        in FastAPI or Starlette, say."""
        if scope["type"] == "lifespan":
            while True:
                msg = await receive()
                if msg["type"] == "lifespan.startup":
                    await send({"type": "lifespan.startup.complete"})
                elif msg["type"] == "lifespan.shutdown":
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        if scope["type"] != "http":
            raise ValueError(f"{type(self).__name__} serves HTTP, not {scope['type']!r}")
        body = bytearray()
        too_large = False
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            if not too_large:
                body += msg.get("body", b"")
                too_large = len(body) > self.max_body
            if not msg.get("more_body", False):
                break
        headers = [(k.decode("latin-1"), v.decode("latin-1")) for k, v in scope.get("headers", [])]
        query = dict(parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True))
        resp = await self.ahandle(
            scope["method"],
            headers,
            bytes(body),
            query=query,
            path=scope.get("path", ""),
            raw=scope,
        )
        await send(
            {
                "type": "http.response.start",
                "status": resp.status,
                # ASGI wants header names lowercased.
                "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in resp.headers],
            }
        )
        await send({"type": "http.response.body", "body": resp.body})

    def wsgi(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        """The handler as a WSGI app, for Flask, Django or any WSGI server: it
        needs a blocking function."""
        if self._is_async:
            raise TypeError(f"{type(self).__name__}: an async function needs asgi, not wsgi")
        stream = environ.get("wsgi.input")
        try:
            length = int(environ.get("CONTENT_LENGTH") or -1)
        except ValueError:
            length = -1
        limit = self.max_body + 1
        body = b""
        if stream is not None:
            if length >= 0:
                body = stream.read(min(length, limit))
            elif environ.get("wsgi.input_terminated"):
                # A server which ends the input itself, for a chunked body.
                body = stream.read(limit)
            # Otherwise no length means no body: reading on would wait for the
            # client to close a kept-alive connection (PEP 3333).
        headers = [(k[5:].replace("_", "-"), v) for k, v in environ.items() if k.startswith("HTTP_")]
        if environ.get("CONTENT_TYPE"):
            headers.append(("Content-Type", environ["CONTENT_TYPE"]))
        if environ.get("CONTENT_LENGTH"):
            headers.append(("Content-Length", environ["CONTENT_LENGTH"]))
        query = dict(parse_qsl(environ.get("QUERY_STRING", ""), keep_blank_values=True))
        resp = self.handle(
            environ.get("REQUEST_METHOD", "GET"),
            headers,
            body,
            query=query,
            path=environ.get("PATH_INFO", ""),
            raw=environ,
        )
        reason = _REASONS.get(resp.status, "OK" if resp.status == 200 else "")
        start_response(f"{resp.status} {reason}".strip(), resp.headers)
        return [resp.body]


def _request(
    method: str,
    headers: Mapping[str, str] | Iterable[tuple[str, str]] | None,
    query: Mapping[str, str] | None,
    path: str,
    raw: Any,
) -> HTTPRequest:
    items = headers.items() if isinstance(headers, Mapping) else (headers or [])
    return HTTPRequest(method=method.upper(), headers=_Headers(items), query=dict(query or {}), path=path, raw=raw)


def json_response(body: bytes, cache: str = "no-store") -> HTTPResponse:
    return HTTPResponse(200, [("Content-Type", "application/json"), ("Cache-Control", cache)], body)
