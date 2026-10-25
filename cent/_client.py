"""Client and AsyncClient: Centrifugo's HTTP server API, blocking and async."""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import secrets
import threading
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from types import TracebackType
from typing import Any, TypeVar

import httpx2

from cent import _broadcast, _core, _deadline
from cent import _wire as _w
from cent._api import BroadcastRequest, _AsyncClientAPI, _ClientAPI
from cent._autobatch import AsyncBatcher, AutoBatch, BatchContext, SyncBatcher
from cent._batch import AsyncBatch, Batch
from cent._broadcast import BroadcastResult, ChannelResult
from cent._core import RequestInfo
from cent._errors import (
    ApiError,
    BroadcastFailedChannelsError,
    CentTimeoutError,
    ClosedError,
    DecodeError,
    InvalidConfigError,
    InvalidRequestError,
    retryable,
)
from cent._retry import BroadcastAttempt, default_delay
from cent._validate import method_of, validate

_T = TypeVar("_T")

DEFAULT_MAX_ATTEMPTS = 2

OnAttemptError = Callable[[BroadcastAttempt], "float | None"]
"""Called by broadcast_with_retry after an attempt which failed in a way a
retry may fix, except the last. It returns the seconds to wait before the next
attempt, or None for the default wait - exponential_backoff(0.1, 5.0) of the
attempt - and may log or count meanwhile. To stop, it raises: its exception
propagates, chained to the broadcast's error (``__cause__``), which carries
the result when Centrifugo replied. The wait never outlasts the call's
timeout."""


def _check_http_client(http_client: Any, want: type[Any], name: str) -> None:
    if http_client is None or isinstance(http_client, want):
        return
    t = type(http_client)
    if t.__module__.split(".")[0] == "httpx":
        raise InvalidConfigError(
            f"http_client is an httpx.{t.__name__}: cent uses httpx2, the maintained fork of httpx with the same API - "
            f"import httpx2, and pass httpx2.{want.__name__}(...)"
        )
    other = "AsyncClient" if name == "Client" else "Client"
    raise InvalidConfigError(
        f"http_client must be an httpx2.{want.__name__} for a {name}, not {t.__name__}; a {other} takes httpx2.{other}"
    )


def _callable(f: Any) -> Any:
    if f is not None and not callable(f):
        raise InvalidConfigError("batch_context must be callable")
    return f


def _auto_batch(auto_batch: Any) -> AutoBatch | None:
    if auto_batch is not None and not isinstance(auto_batch, AutoBatch):
        raise InvalidConfigError("auto_batch must be a cent.AutoBatch")
    return auto_batch


def _idempotency_key() -> str:
    return "pycent-" + secrets.token_urlsafe(18)


def _retry_options(request: BroadcastRequest, max_attempts: int, attempt_timeout: float | None) -> None:
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise InvalidRequestError("invalid broadcast request: max_attempts must be 1 or more")
    if attempt_timeout is not None and (
        isinstance(attempt_timeout, bool) or not isinstance(attempt_timeout, (int, float)) or attempt_timeout <= 0
    ):
        raise InvalidRequestError("invalid broadcast request: attempt_timeout must be positive")
    validate(request)


class _RetryState:
    """The outcome of broadcast_with_retry's attempts so far."""

    def __init__(self, request: BroadcastRequest) -> None:
        self.channels = list(request.channels)
        self.key = request.idempotency_key or _idempotency_key()
        self.final = BroadcastResult(
            channels=[ChannelResult(channel=ch) for ch in self.channels], idempotency_key=self.key
        )
        # Positions in channels of what the next attempt sends: positions, not
        # names, so that a channel listed twice keeps both entries.
        self.pending = list(range(len(self.channels)))
        self.replied = False

    def attempt_request(self, request: BroadcastRequest) -> BroadcastRequest:
        return dataclasses.replace(request, channels=[self.channels[p] for p in self.pending], idempotency_key=self.key)

    def record(self, res: BroadcastResult, err: Exception | None) -> None:
        self.final.attempts += 1
        for i, pos in enumerate(self.pending):
            tried = self.final.channels[pos].attempts
            ch = res.channels[i]
            ch.attempts = tried + 1
            self.final.channels[pos] = ch
        if err is None or isinstance(err, BroadcastFailedChannelsError):
            self.replied = True
        self.final.replied = self.replied

    def next_channels(self, res: BroadcastResult) -> list[ChannelResult]:
        """Keeps in pending the channels which may still succeed, and returns them."""
        self.pending = [
            pos for i, pos in enumerate(self.pending) if (e := res.channels[i].error) is not None and retryable(e)
        ]
        return [self.final.channels[p] for p in self.pending]

    def outcome(self, last: Exception | None) -> BroadcastResult:
        """The final result, or the error to raise: BroadcastFailedChannelsError
        when some attempt got a reply, the last attempt's error otherwise."""
        if not self.replied:
            if last is None:  # pragma: no cover - an attempt which failed as a whole leaves its error
                raise RuntimeError("cent: broadcast_with_retry: no reply and no error")
            raise last
        return _broadcast.check(self.final)


def _attempt_result(request: BroadcastRequest, err: Exception) -> BroadcastResult:
    if isinstance(err, BroadcastFailedChannelsError):
        return err.result
    return _broadcast.failed_as_whole(request.channels, err, 1)


class _Calls:
    """The calls in progress of a Client, so that close can wait for them."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._active = 0
        self.closed = False

    def __enter__(self) -> None:
        with self._cond:
            if self.closed:
                raise ClosedError("client closed")
            self._active += 1

    def __exit__(self, *exc: object) -> None:
        self.leave()

    def add(self) -> None:
        """Counts in work going on for calls already counted - an automatic
        batch which outlives its callers - closed or not."""
        with self._cond:
            self._active += 1

    def leave(self) -> None:
        with self._cond:
            self._active -= 1
            if self._active == 0:
                self._cond.notify_all()

    def close(self, timeout: float | None) -> bool:
        with self._cond:
            self.closed = True
            return self._cond.wait_for(lambda: self._active == 0, timeout)


class _AsyncCalls:
    """The calls in progress of an AsyncClient."""

    def __init__(self) -> None:
        self._active = 0
        self._idle: asyncio.Event | None = None
        self.closed = False

    def __enter__(self) -> None:
        if self.closed:
            raise ClosedError("client closed")
        self._active += 1

    def __exit__(self, *exc: object) -> None:
        self.leave()

    def add(self) -> None:
        self._active += 1

    def leave(self) -> None:
        self._active -= 1
        if self._active == 0 and self._idle is not None:
            self._idle.set()

    async def close(self, timeout: float | None) -> bool:
        self.closed = True
        if self._active == 0:
            return True
        if self._idle is None:
            self._idle = asyncio.Event()
        try:
            async with asyncio.timeout(timeout):
                await self._idle.wait()
        except TimeoutError:
            return False
        return True


def _read(chunks: Iterator[bytes], deadline: float, method: str, limit: int = -1) -> bytes:
    """A body, read until it ends - or limit bytes - and the deadline checked
    between its chunks: each read is bounded by the time left when the request
    started, and a reply arriving in pieces stops at the deadline."""
    out = bytearray()
    for chunk in chunks:
        out += chunk
        if 0 <= limit <= len(out):
            return bytes(out[:limit])
        if time.monotonic() > deadline:
            raise CentTimeoutError(f"{method}: timed out reading the reply")
    return bytes(out)


async def _aread(chunks: AsyncIterator[bytes], limit: int = -1) -> bytes:
    out = bytearray()
    async for chunk in chunks:
        out += chunk
        if 0 <= limit <= len(out):
            return bytes(out[:limit])
    return bytes(out)


class Client(_ClientAPI):
    """Calls Centrifugo's HTTP server API. Safe for concurrent use from
    threads, and meant to be created once and shared:

    >>> client = cent.Client("http://localhost:8000/api", api_key=os.environ["CENTRIFUGO_API_KEY"])
    >>> client.publish(cent.PublishRequest(channel="news", data={"text": "hello"}))

    Every API method takes its request and returns its result, raising unless
    Centrifugo did everything asked. Each takes ``timeout``, in seconds; without
    one, request_timeout bounds the call.

    Options:

    - api_endpoint: the base URL of the API, "http://localhost:8000/api". Each
      method is sent to it plus its name, "/publish".
    - api_endpoint_func: instead of api_endpoint, a function returning it for
      each request, for addresses discovered rather than fixed.
    - api_key: sent as X-API-Key. Leave it and bearer_token_func unset when
      requests are authenticated another way - mutual TLS, a proxy - or not
      at all.
    - bearer_token_func: returns the token sent as "Authorization: Bearer"
      with each request, for Centrifugo PRO's JWKS authentication of the API
      - cent.token.APITokens.token, say. Not together with api_key.
    - http_client: the httpx2.Client sending requests - httpx2 is the maintained
      fork of httpx, with the same API. It is never changed:
      credentials and headers go on each request. Without one, the client
      keeps up to 256 connections to a host alive, never follows redirects,
      and closes idle connections after 50 seconds.
    - request_timeout: seconds bounding a call without a timeout of its own,
      10 by default.
    - headers: extra headers for every request, for a proxy in front of
      Centrifugo. Not X-API-Key, Authorization or Content-Type. A User-Agent
      replaces cent's.
    - on_request: called after every HTTP request with a RequestInfo, for
      metrics without a dependency of cent's. It runs in the calling thread,
      and the call waits for it.
    - auto_batch: sends calls made concurrently in batches - see AutoBatch.
    - batch_context: with auto_batch, makes the context of a batch's request
      from its callers' - for a tracing span linking every caller's - see
      BatchContext. Without it, a batch runs in a context of its own, carrying
      no caller's values.
    """

    def __init__(
        self,
        api_endpoint: str | None = None,
        *,
        api_endpoint_func: Callable[[], str] | None = None,
        api_key: str = "",
        bearer_token_func: Callable[[], str] | None = None,
        http_client: httpx2.Client | None = None,
        request_timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
        on_request: Callable[[RequestInfo], None] | None = None,
        auto_batch: AutoBatch | None = None,
        batch_context: BatchContext | None = None,
    ) -> None:
        self._cfg = _core.Config(
            api_endpoint=api_endpoint,
            api_endpoint_func=api_endpoint_func,
            api_key=api_key,
            bearer_token_func=bearer_token_func,
            request_timeout=request_timeout,
            headers=headers,
            on_request=on_request,
        )
        _check_http_client(http_client, httpx2.Client, "Client")
        self._own_http = http_client is None
        self._http = http_client if http_client is not None else _core.default_http_client()
        self._calls = _Calls()
        ab = _auto_batch(auto_batch)
        self._batcher = SyncBatcher(self, ab, _callable(batch_context)) if ab is not None else None

    # Sending.

    def _roundtrip(self, method: str, make_body: Callable[[], bytes], deadline: float, info: RequestInfo) -> bytes:
        cfg = self._cfg
        base = cfg.endpoint
        if cfg.endpoint_func is not None:
            base = _core.checked_endpoint(cfg.endpoint_func())
        token = _core.checked_token(cfg.token_func()) if cfg.token_func is not None else None
        body = make_body()
        left = _core.remaining(deadline, method)
        bound = _deadline.deadline.set(deadline)
        try:
            with self._http.stream(
                "POST",
                f"{base}/{method}",
                content=body,
                headers=cfg.request_headers(token),
                timeout=httpx2.Timeout(left),
            ) as resp:
                info.status_code = resp.status_code
                if resp.status_code != 200:
                    chunks = resp.iter_bytes()
                    data = _read(chunks, deadline, method, _core.MAX_API_ERROR_BYTES)
                    _read(chunks, deadline, method, _core.MAX_DRAIN_BYTES)
                    raise _core.http_error(method, resp.status_code, data, resp.headers)
                return _read(resp.iter_bytes(), deadline, method)
        except httpx2.DecodingError as e:
            raise DecodeError(f"{method}: the reply cannot be decoded: {e}") from e
        except httpx2.HTTPError as e:
            raise _core.transport_error(method, e) from e
        finally:
            _deadline.deadline.reset(bound)

    def _call(
        self,
        method: str,
        make_body: Callable[[], bytes],
        *,
        commands: int,
        deadline: float,
        parse: Callable[[bytes], tuple[_T, int]],
        auto: bool = False,
    ) -> _T:
        info = RequestInfo(method=method, commands=commands, auto_batch=auto)
        start = time.monotonic()
        try:
            out, info.failed = parse(self._roundtrip(method, make_body, deadline, info))
        except Exception as e:
            self._cfg.report(info, start, e)
            raise
        self._cfg.report(info, start, None)
        return out

    def _result(self, request: Any, timeout: float | None) -> dict[str, Any]:
        method = method_of(request)
        validate(request)
        deadline = self._cfg.deadline(timeout)

        def parse(raw: bytes) -> tuple[tuple[dict[str, Any], ApiError | None], int]:
            result, err = _core.envelope(raw, method)
            return (result, err), 0 if err is None else 1

        def alone() -> tuple[dict[str, Any], ApiError | None]:
            return self._call(
                method, lambda: _w.encode(request._to_wire(), method), commands=1, deadline=deadline, parse=parse
            )

        with self._calls:
            if self._batcher is None:
                result, err = alone()
            else:
                went_alone, out = self._batcher.call(method, request, deadline, alone)
                if went_alone:
                    result, err = out
                else:
                    index, reply = out
                    err = _core.command_error(reply, index, method)
                    result = _w.obj(reply.get(method) or {}, f"replies[{index}].{method}")
        if err is not None:
            raise err
        return result

    def _invoke(self, request: Any, result: type[_T], timeout: float | None) -> _T:
        out: _T = result._from_wire(self._result(request, timeout))  # type: ignore[attr-defined]
        return out

    def _send_batch(
        self,
        body: bytes | None,
        n: int,
        parse: Callable[[bytes], tuple[list[dict[str, Any]], int]],
        timeout: float | None,
    ) -> list[dict[str, Any]]:
        with self._calls:
            if body is None:
                return []
            return self._call("batch", lambda: body, commands=n, deadline=self._cfg.deadline(timeout), parse=parse)

    def _send_auto_batch(self, body: bytes, n: int, timeout: float) -> list[dict[str, Any]]:
        """An automatic batch: counted as a call by its batcher, closed or not."""

        def parse(raw: bytes) -> tuple[list[dict[str, Any]], int]:
            replies = _core.batch_replies(raw, n)
            return replies, sum(1 for r in replies if r.get("error") is not None)

        return self._call(
            "batch", lambda: body, commands=n, deadline=time.monotonic() + timeout, parse=parse, auto=True
        )

    # Broadcast.

    def broadcast(self, request: BroadcastRequest, *, timeout: float | None = None) -> BroadcastResult:
        """Publishes the same data into many channels in one request.

        Channels succeed or fail on their own. It returns when every channel
        got the publication. When Centrifugo carried the broadcast out and one
        or more channels failed - up to all of them - it raises
        BroadcastFailedChannelsError, whose ``result`` holds every channel's
        outcome. Any other error means it failed as a whole: no channel got a
        reply. After a timeout or a network error Centrifugo may still have
        published it.

        To go on despite some failed channels::

            try:
                client.broadcast(request)
            except cent.BroadcastFailedChannelsError as e:
                log.warning("broadcast failed in %s", e.result.failed())

        Retry it with broadcast_with_retry, which sends again only the
        channels which may still succeed, with one idempotency_key.
        """
        raw = self._result(request, timeout)
        return _broadcast.check(_broadcast.from_wire(raw, list(request.channels), request.idempotency_key))

    def broadcast_with_retry(
        self,
        request: BroadcastRequest,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        attempt_timeout: float | None = None,
        on_attempt_error: OnAttemptError | None = None,
        timeout: float | None = None,
    ) -> BroadcastResult:
        """Broadcasts as broadcast does, and retries the channels which failed for
        a temporary reason - see retryable - up to max_attempts (2 by default:
        one retry).

        - Only the channels which may still succeed are sent again; when only
          channels which failed for good are left, it stops.
        - Every attempt carries the same idempotency_key - made for the call
          when the request has none - so that a channel which got the
          publication in an earlier attempt does not get it again. The memory,
          Redis and PostgreSQL brokers keep keys; the NATS broker ignores them,
          and a retry may publish again.
        - The result holds every channel's last outcome, and the key: retrying
          later with it publishes only into the channels which did not get it.

        timeout bounds the whole call, waits included (request_timeout when
        None), attempt_timeout each attempt. on_attempt_error decides the wait
        between attempts, and may stop them: see OnAttemptError. It raises as
        broadcast does.
        """
        _retry_options(request, max_attempts, attempt_timeout)
        deadline = self._cfg.deadline(timeout)
        state = _RetryState(request)
        last: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            left = deadline - time.monotonic()
            if left <= 0:
                last = last or CentTimeoutError("broadcast: timed out")
                break
            attempt_req = state.attempt_request(request)
            per = left if attempt_timeout is None else min(left, attempt_timeout)
            try:
                res = self.broadcast(attempt_req, timeout=per)
                err: Exception | None = None
            except InvalidRequestError:
                raise
            except Exception as e:
                res, err = _attempt_result(attempt_req, e), e
            state.record(res, err)
            last = err
            # An ended deadline leaves no time for another attempt.
            if err is None or not retryable(err) or attempt == max_attempts or time.monotonic() >= deadline:
                break
            retry = state.next_channels(res)
            a = BroadcastAttempt(attempt=attempt, error=err, retry=retry, result=state.final, idempotency_key=state.key)
            try:
                wait = on_attempt_error(a) if on_attempt_error is not None else None
            except Exception as stop:
                try:
                    state.outcome(last)
                except Exception as final:
                    raise stop from final
                raise
            delay = default_delay(attempt) if wait is None else wait
            time.sleep(max(0.0, min(delay, deadline - time.monotonic())))
        return state.outcome(last)

    # Batches.

    def new_batch(self, *, parallel: bool = False) -> Batch:
        """An empty Batch sent by this client. Without parallel the commands run
        one by one, in the order added - but Centrifugo PRO sends a sequential
        batch's publications to its broker together: each channel's take
        effect in order, publications into different channels may not, unless
        the namespace sets publication_grouping_disabled. With parallel,
        Centrifugo runs them concurrently, with no order."""
        return Batch(self, parallel)

    # Shutdown.

    def close(self, timeout: float | None = None) -> None:
        """Stops the client: calls made from now on raise ClosedError, and close
        waits for the calls in progress to end. A broadcast being retried stops
        at its next attempt. It raises CentTimeoutError when timeout, in
        seconds, passes first; the calls left go on then, and close may be
        called again. With its default HTTP client it then closes its
        connections.

        Call it when the application shuts down, so that what was accepted is
        sent before the process exits. A Client is also a context manager
        closing it."""
        if not self._calls.close(timeout):
            raise CentTimeoutError("close: calls still in progress")
        if self._own_http:
            self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        self.close()


async def _maybe_await(v: Any) -> Any:
    if inspect.isawaitable(v):
        return await v
    return v


class AsyncClient(_AsyncClientAPI):
    """Calls Centrifugo's HTTP server API from asyncio code, as Client does:
    the same methods - awaited - options, errors and behaviour.

    >>> async with cent.AsyncClient("http://localhost:8000/api", api_key=key) as client:
    ...     await client.publish(cent.PublishRequest(channel="news", data={"text": "hello"}))

    api_endpoint_func and bearer_token_func may be coroutine functions.
    http_client is an httpx2.AsyncClient. A call's timeout bounds it; an
    asyncio.timeout around it, or cancelling its task, ends it sooner.
    """

    def __init__(
        self,
        api_endpoint: str | None = None,
        *,
        api_endpoint_func: Callable[[], str | Awaitable[str]] | None = None,
        api_key: str = "",
        bearer_token_func: Callable[[], str | Awaitable[str]] | None = None,
        http_client: httpx2.AsyncClient | None = None,
        request_timeout: float | None = None,
        headers: Mapping[str, str] | None = None,
        on_request: Callable[[RequestInfo], None] | None = None,
        auto_batch: AutoBatch | None = None,
        batch_context: BatchContext | None = None,
    ) -> None:
        self._cfg = _core.Config(
            api_endpoint=api_endpoint,
            api_endpoint_func=api_endpoint_func,
            api_key=api_key,
            bearer_token_func=bearer_token_func,
            request_timeout=request_timeout,
            headers=headers,
            on_request=on_request,
        )
        _check_http_client(http_client, httpx2.AsyncClient, "AsyncClient")
        self._own_http = http_client is None
        self._http = http_client if http_client is not None else _core.default_async_http_client()
        self._calls = _AsyncCalls()
        ab = _auto_batch(auto_batch)
        self._batcher = AsyncBatcher(self, ab, _callable(batch_context)) if ab is not None else None

    async def _roundtrip(
        self, method: str, make_body: Callable[[], bytes], deadline: float, info: RequestInfo
    ) -> bytes:
        cfg = self._cfg
        left = _core.remaining(deadline, method)
        timer = asyncio.timeout(left)
        try:
            async with timer:
                base = cfg.endpoint
                if cfg.endpoint_func is not None:
                    base = _core.checked_endpoint(await _maybe_await(cfg.endpoint_func()))
                token = None
                if cfg.token_func is not None:
                    token = _core.checked_token(await _maybe_await(cfg.token_func()))
                body = make_body()
                async with self._http.stream(
                    "POST",
                    f"{base}/{method}",
                    content=body,
                    headers=cfg.request_headers(token),
                    timeout=httpx2.Timeout(left),
                ) as resp:
                    info.status_code = resp.status_code
                    if resp.status_code != 200:
                        chunks = resp.aiter_bytes()
                        data = await _aread(chunks, _core.MAX_API_ERROR_BYTES)
                        await _aread(chunks, _core.MAX_DRAIN_BYTES)
                        raise _core.http_error(method, resp.status_code, data, resp.headers)
                    return await resp.aread()
        except httpx2.DecodingError as e:
            raise DecodeError(f"{method}: the reply cannot be decoded: {e}") from e
        except httpx2.HTTPError as e:
            raise _core.transport_error(method, e) from e
        except TimeoutError as e:
            if timer.expired() and not isinstance(e, CentTimeoutError):
                raise CentTimeoutError(f"{method}: timed out") from e
            raise

    async def _call(
        self,
        method: str,
        make_body: Callable[[], bytes],
        *,
        commands: int,
        deadline: float,
        parse: Callable[[bytes], tuple[_T, int]],
        auto: bool = False,
    ) -> _T:
        info = RequestInfo(method=method, commands=commands, auto_batch=auto)
        start = time.monotonic()
        try:
            out, info.failed = parse(await self._roundtrip(method, make_body, deadline, info))
        except Exception as e:
            self._cfg.report(info, start, e)
            raise
        self._cfg.report(info, start, None)
        return out

    async def _result(self, request: Any, timeout: float | None) -> dict[str, Any]:
        method = method_of(request)
        validate(request)
        deadline = self._cfg.deadline(timeout)

        def parse(raw: bytes) -> tuple[tuple[dict[str, Any], ApiError | None], int]:
            result, err = _core.envelope(raw, method)
            return (result, err), 0 if err is None else 1

        async def alone() -> tuple[dict[str, Any], ApiError | None]:
            return await self._call(
                method, lambda: _w.encode(request._to_wire(), method), commands=1, deadline=deadline, parse=parse
            )

        with self._calls:
            if self._batcher is None:
                result, err = await alone()
            else:
                went_alone, out = await self._batcher.call(method, request, deadline, alone)
                if went_alone:
                    result, err = out
                else:
                    index, reply = out
                    err = _core.command_error(reply, index, method)
                    result = _w.obj(reply.get(method) or {}, f"replies[{index}].{method}")
        if err is not None:
            raise err
        return result

    async def _invoke(self, request: Any, result: type[_T], timeout: float | None) -> _T:
        out: _T = result._from_wire(await self._result(request, timeout))  # type: ignore[attr-defined]
        return out

    async def _send_batch(
        self,
        body: bytes | None,
        n: int,
        parse: Callable[[bytes], tuple[list[dict[str, Any]], int]],
        timeout: float | None,
    ) -> list[dict[str, Any]]:
        with self._calls:
            if body is None:
                return []
            return await self._call(
                "batch", lambda: body, commands=n, deadline=self._cfg.deadline(timeout), parse=parse
            )

    async def _send_auto_batch(self, body: bytes, n: int, timeout: float) -> list[dict[str, Any]]:
        """An automatic batch: counted as a call by its batcher, closed or not."""

        def parse(raw: bytes) -> tuple[list[dict[str, Any]], int]:
            replies = _core.batch_replies(raw, n)
            return replies, sum(1 for r in replies if r.get("error") is not None)

        return await self._call(
            "batch", lambda: body, commands=n, deadline=time.monotonic() + timeout, parse=parse, auto=True
        )

    async def broadcast(self, request: BroadcastRequest, *, timeout: float | None = None) -> BroadcastResult:
        """Publishes the same data into many channels in one request, as
        Client.broadcast does."""
        raw = await self._result(request, timeout)
        return _broadcast.check(_broadcast.from_wire(raw, list(request.channels), request.idempotency_key))

    async def broadcast_with_retry(
        self,
        request: BroadcastRequest,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
        attempt_timeout: float | None = None,
        on_attempt_error: OnAttemptError | None = None,
        timeout: float | None = None,
    ) -> BroadcastResult:
        """Broadcasts and retries the channels which may still succeed, as
        Client.broadcast_with_retry does."""
        _retry_options(request, max_attempts, attempt_timeout)
        deadline = self._cfg.deadline(timeout)
        state = _RetryState(request)
        last: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            left = deadline - time.monotonic()
            if left <= 0:
                last = last or CentTimeoutError("broadcast: timed out")
                break
            attempt_req = state.attempt_request(request)
            per = left if attempt_timeout is None else min(left, attempt_timeout)
            try:
                res = await self.broadcast(attempt_req, timeout=per)
                err: Exception | None = None
            except InvalidRequestError:
                raise
            except Exception as e:
                res, err = _attempt_result(attempt_req, e), e
            state.record(res, err)
            last = err
            # An ended deadline leaves no time for another attempt.
            if err is None or not retryable(err) or attempt == max_attempts or time.monotonic() >= deadline:
                break
            retry = state.next_channels(res)
            a = BroadcastAttempt(attempt=attempt, error=err, retry=retry, result=state.final, idempotency_key=state.key)
            try:
                wait = on_attempt_error(a) if on_attempt_error is not None else None
            except Exception as stop:
                try:
                    state.outcome(last)
                except Exception as final:
                    raise stop from final
                raise
            delay = default_delay(attempt) if wait is None else wait
            await asyncio.sleep(max(0.0, min(delay, deadline - time.monotonic())))
        return state.outcome(last)

    def new_batch(self, *, parallel: bool = False) -> AsyncBatch:
        """An empty AsyncBatch sent by this client, as Client.new_batch."""
        return AsyncBatch(self, parallel)

    async def aclose(self, timeout: float | None = None) -> None:
        """Stops the client and waits for the calls in progress, as Client.close
        does."""
        if not await self._calls.close(timeout):
            raise CentTimeoutError("aclose: calls still in progress")
        if self._own_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        await self.aclose()
