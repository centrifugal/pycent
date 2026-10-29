"""Batches: commands sent to Centrifugo in one request."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from cent import _broadcast, _core
from cent import _wire as _w
from cent._api import BroadcastRequest, _BatchAPI
from cent._errors import (
    BatchFailedCommandsError,
    BatchNotSentError,
    BatchSentError,
    CentError,
    FailedCommand,
    InvalidRequestError,
)
from cent._validate import method_of, validate

if TYPE_CHECKING:
    from cent._broadcast import BroadcastResult
    from cent._client import AsyncClient, Client

_T = TypeVar("_T")


class BatchResult:
    """The outcome of a sent batch as a whole. Each command's own outcome is in
    the Pending its method returned."""

    __slots__ = ("_failed", "replied")

    def __init__(self, replied: bool, failed: list[FailedCommand]) -> None:
        # True when Centrifugo replied to every command, the failed ones
        # included; False when the batch failed as a whole. True for an empty
        # batch.
        self.replied = replied
        self._failed = failed

    @property
    def failed(self) -> list[FailedCommand]:
        """The commands which failed, with their errors, in the order they were
        added - as the error's ``failed`` lists them. When the batch failed as a
        whole, that is every command."""
        return list(self._failed)

    def __repr__(self) -> str:
        return f"BatchResult(replied={self.replied}, failed={len(self._failed)})"


class Pending(Generic[_T]):
    """The outcome of one command of a batch, available once the batch is sent."""

    __slots__ = ("_batch", "_get", "_index")

    def __init__(self, batch: _BatchBase | None, index: int, get: Callable[[dict[str, Any]], _T]) -> None:
        self._batch = batch
        self._index = index
        self._get = get

    @classmethod
    def resolved(cls, result: _T | None = None, error: Exception | None = None) -> Pending[_T]:
        """A Pending of no batch, whose result() returns result or raises error:
        for test doubles of code which reads a batch's outcomes."""

        def get(_: dict[str, Any]) -> _T:
            if error is not None:
                raise error
            return result  # type: ignore[return-value]

        return cls(None, 0, get)

    def result(self) -> _T:
        """The command's result, or its error raised: an ApiError for this
        command, the error which failed the whole batch, or BatchNotSentError.
        A broadcast raises BroadcastFailedChannelsError, carrying every
        channel's outcome, when any channel failed."""
        b = self._batch
        if b is None:
            return self._get({})
        if not b._sent:
            raise BatchNotSentError("batch not sent yet")
        if b._error is not None:
            raise b._error
        if (err := b._command_errors[self._index]) is not None:
            raise err
        return self._get(b._replies[self._index])


class _BatchBase(_BatchAPI):
    def __init__(self, parallel: bool) -> None:
        self._parallel = parallel
        self._commands: list[str] = []
        self._methods: list[str] = []
        # Per command: how to tell from a successful reply that a part of it
        # failed - a broadcast's channels.
        self._checks: list[Callable[[dict[str, Any]], None] | None] = []
        self._invalid: list[InvalidRequestError | None] = []
        self._replies: list[dict[str, Any]] = []
        self._command_errors: list[Exception | None] = []
        self._error: Exception | None = None
        self._sent = False

    def __len__(self) -> int:
        return len(self._commands)

    def _append(self, request: Any, check: Callable[[dict[str, Any]], None] | None) -> int:
        if self._sent:
            raise RuntimeError("cent: command added to a batch that was already sent")
        method = method_of(request)
        invalid: InvalidRequestError | None = None
        text = ""
        try:
            validate(request)
            text = _w.encode({method: request._to_wire()}, method).decode("utf-8")
        except InvalidRequestError as e:
            invalid = e
        self._commands.append(text)
        self._methods.append(method)
        self._checks.append(check)
        self._invalid.append(invalid)
        return len(self._commands) - 1

    def _add(self, request: Any, result: type[_T]) -> Pending[_T]:
        index = self._append(request, None)
        from_wire: Callable[[Any, str], _T] = result._from_wire  # type: ignore[attr-defined]
        method = self._methods[index]
        return Pending(self, index, lambda r: from_wire(r.get(method) or {}, f"replies[{index}].{method}"))

    def _add_broadcast(self, request: BroadcastRequest) -> Pending[BroadcastResult]:
        """Adds a broadcast command: its outcome is every channel's, and
        BroadcastFailedChannelsError when any channel failed."""
        channels = list(request.channels)
        key = request.idempotency_key
        cache: list[BroadcastResult | Exception] = []

        # Built once, on first use - by send's check or by Pending.result -
        # and shared, so that send's BatchFailedCommandsError holds the very
        # BroadcastFailedChannelsError which Pending.result raises.
        def get(r: dict[str, Any]) -> BroadcastResult:
            if not cache:
                try:
                    cache.append(_broadcast.check(_broadcast.from_wire(r.get("broadcast") or {}, channels, key)))
                except CentError as e:
                    cache.append(e)
            out = cache[0]
            if isinstance(out, Exception):
                raise out
            return out

        def check(r: dict[str, Any]) -> None:
            get(r)

        index = self._append(request, check)
        return Pending(self, index, get)

    def _prepare(self) -> bytes | None:
        """The batch's body, or None for an empty batch."""
        if self._sent:
            raise BatchSentError("batch already sent")
        self._sent = True
        if not self._commands:
            return None
        for i, err in enumerate(self._invalid):
            if err is not None:
                e = InvalidRequestError(f"batch command #{i}: {err}")
                e.__cause__ = err.__cause__
                raise e
        parallel = ',"parallel":true' if self._parallel else ""
        return ('{"commands":[' + ",".join(self._commands) + "]" + parallel + "}").encode("utf-8")

    def _parse(self, raw: bytes) -> tuple[list[dict[str, Any]], int]:
        replies = _core.batch_replies(raw, len(self._commands))
        return replies, sum(1 for r in replies if r.get("error") is not None)

    def _finish(self, replies: list[dict[str, Any]]) -> BatchResult:
        self._replies = replies
        failed: list[FailedCommand] = []
        for i, r in enumerate(replies):
            err: Exception | None = _core.command_error(r, i, self._methods[i])
            self._command_errors.append(err)
            check = self._checks[i]
            if err is None and check is not None:
                try:
                    check(r)
                except CentError as e:
                    err = e
            if err is not None:
                failed.append(FailedCommand(i, self._methods[i], err))
        res = BatchResult(True, failed)
        if failed:
            raise BatchFailedCommandsError(failed, len(replies), res)
        return res

    def _fail(self, err: BaseException) -> None:
        # A cancelled send leaves the batch's outcome unknown, as a timeout
        # does: Centrifugo may have run it.
        self._error = err if isinstance(err, Exception) else CentError(f"batch send interrupted: {err!r}")


class Batch(_BatchBase):
    """Commands sent to Centrifugo in one request. Create one with
    Client.new_batch, add commands with its methods - one per API method, each
    returning a Pending - then call send:

    >>> batch = client.new_batch()
    >>> pub = batch.publish(channel="news", data={"text": "hi"})
    >>> stats = batch.presence_stats(channel="news")
    >>> batch.send()  # raises unless every command succeeded
    >>> pub.result()

    A batch is sent once, and is not safe for concurrent use.
    """

    def __init__(self, client: Client, parallel: bool) -> None:
        super().__init__(parallel)
        self._client = client

    def send(self, *, timeout: float | None = None) -> BatchResult:
        """Sends the batch and waits for Centrifugo's reply to every command.

        It returns when every command succeeded. BatchFailedCommandsError means
        one or more commands failed, up to all: every command got its own
        reply, each Pending holds its outcome. Any other error means the batch
        failed as a whole: no command got a reply, and every Pending raises
        that error. A command the client can tell is invalid fails the whole
        batch before anything is sent. An empty batch sends nothing.
        """
        try:
            body = self._prepare()
            replies = self._client._send_batch(body, len(self._commands), self._parse, timeout)
        except BatchSentError:
            raise
        except BaseException as e:
            self._fail(e)
            raise
        return self._finish(replies)


class AsyncBatch(_BatchBase):
    """A batch of an AsyncClient: as Batch, with ``await batch.send()``."""

    def __init__(self, client: AsyncClient, parallel: bool) -> None:
        super().__init__(parallel)
        self._client = client

    async def send(self, *, timeout: float | None = None) -> BatchResult:
        """Sends the batch, as Batch.send does."""
        try:
            body = self._prepare()
            replies = await self._client._send_batch(body, len(self._commands), self._parse, timeout)
        except BatchSentError:
            raise
        except BaseException as e:
            self._fail(e)
            raise
        return self._finish(replies)
