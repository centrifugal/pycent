"""Automatic batching: calls made concurrently, sent together once enough are in
flight. See AutoBatch."""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from cent import _core
from cent import _wire as _w
from cent._errors import CentTimeoutError, InvalidConfigError

_T = TypeVar("_T")


@dataclass(frozen=True, slots=True)
class AutoBatch:
    """Lets a client send concurrent calls together, as one batch request, once
    enough of them are in flight.

    Nothing waits for a batch to fill. While fewer than max_in_flight requests
    are in flight, every call is sent at once, alone, exactly as without
    AutoBatch. Only a call made when max_in_flight requests are already in
    flight waits - for one of them to finish, not for a timer. Then all the
    calls waiting at that moment go out together, at most max_batch_size of
    them. The busier the client, the larger the batches, and the fewer
    requests Centrifugo handles for the same work.

    Every call gets its own command's reply. Calls made one after another keep
    their order: a call waits for its reply, so the next one joins a later
    batch. Calls sharing a batch were made concurrently, with no order between
    them, and Centrifugo runs them in parallel.

    Calls sharing a batch share its request, though: when it fails as a whole
    - the network, the credentials, a body too large for a proxy in front of
    Centrifugo (nginx refuses bodies over 1 MB by default) - every call in it
    fails with that error. Each call keeps its own timeout: the batch lasts
    until the latest of its calls'.

    A smaller max_in_flight batches more: a value above the concurrency the
    load needs leaves nearly every call sent alone. Something like 8 suits
    most applications.
    """

    max_in_flight: int
    """How many requests may be in flight before calls start to wait and be batched."""

    max_batch_size: int = _core.DEFAULT_MAX_BATCH_SIZE
    """The most calls one batch carries."""

    def __post_init__(self) -> None:
        if isinstance(self.max_in_flight, bool) or not isinstance(self.max_in_flight, int) or self.max_in_flight < 1:
            raise InvalidConfigError("AutoBatch.max_in_flight must be 1 or more; leave auto_batch unset to disable it")
        if isinstance(self.max_batch_size, bool) or not isinstance(self.max_batch_size, int) or self.max_batch_size < 2:
            raise InvalidConfigError("AutoBatch.max_batch_size must be 2 or more: a batch of 1 never batches")


class _Queued:
    """A call waiting to be sent in a batch. Until done, its fields belong to the
    batcher; afterwards, to the caller."""

    __slots__ = ("command", "deadline", "done", "error", "gone", "reply", "taken")

    def __init__(self, command: str, deadline: float, done: Any) -> None:
        # Encoded before it queued: the batch never reads the caller's request.
        self.command = command
        self.deadline = deadline
        self.done = done
        self.reply: dict[str, Any] = {}
        self.error: Exception | None = None
        # taken once in a batch; gone once its caller gave up before that.
        self.taken = False
        self.gone = False


def _encode(method: str, request: Any) -> str:
    return _w.encode({method: request._to_wire()}, method).decode("utf-8")


def _take(queue: deque[_Queued], max_batch: int) -> list[_Queued]:
    """Takes up to max_batch calls off the head of queue, skipping those gone."""
    items: list[_Queued] = []
    while queue and len(items) < max_batch:
        q = queue.popleft()
        if q.gone:
            continue
        q.taken = True
        items.append(q)
    return items


def _drop_gone(queue: deque[_Queued]) -> None:
    while queue and queue[0].gone:
        queue.popleft()


def _batch_body(items: list[_Queued]) -> bytes:
    # Parallel: the calls of an automatic batch were made concurrently, so
    # nothing orders them, and Centrifugo pipelines their broker commands.
    return ('{"commands":[' + ",".join(q.command for q in items) + '],"parallel":true}').encode("utf-8")


def _batch_deadline(items: list[_Queued], request_timeout: float) -> float:
    """The latest deadline of the calls, never less than request_timeout from now."""
    return max([time.monotonic() + request_timeout, *(q.deadline for q in items)])


class SyncBatcher:
    """AutoBatch for Client, with threads."""

    def __init__(self, client: Any, opts: AutoBatch) -> None:
        self._client = client
        self._max_in_flight = opts.max_in_flight
        self._max_batch = opts.max_batch_size
        self._lock = threading.Lock()
        self._in_flight = 0
        self._queue: deque[_Queued] = deque()

    def call(self, method: str, request: Any, deadline: float, alone: Callable[[], _T]) -> tuple[bool, Any]:
        """(True, what alone returned) when a slot was free and the call went
        alone; (False, its command's reply) when it went in a batch."""
        command: str | None = None
        q: _Queued | None = None
        with self._lock:
            while True:
                _drop_gone(self._queue)
                if self._in_flight < self._max_in_flight and not self._queue:
                    self._in_flight += 1
                    break
                if command is not None:
                    q = _Queued(command, deadline, threading.Event())
                    self._queue.append(q)
                    break
                # The call will queue: encode its command first, outside the
                # lock, then look again - a slot may have freed meanwhile, and
                # a call must never queue while one is free.
                self._lock.release()
                try:
                    command = _encode(method, request)
                finally:
                    self._lock.acquire()
        if q is None:
            try:
                return True, alone()
            finally:
                self._release()
        return False, self._wait(q, method, deadline)

    def _wait(self, q: _Queued, method: str, deadline: float) -> dict[str, Any]:
        if not q.done.wait(max(0.0, deadline - time.monotonic())):
            with self._lock:
                taken = q.taken
                if not taken:
                    q.gone = True
            if not q.done.is_set():
                if taken:
                    # Sent: whether it took effect is unknown to this caller.
                    raise CentTimeoutError(f"{method}: timed out")
                raise CentTimeoutError(f"{method}: timed out before it was sent")
            # The reply came as the deadline ended: it is the call's outcome.
        if q.error is not None:
            raise q.error
        return q.reply

    def _release(self) -> None:
        """Hands the slot of a finished request to the calls waiting, if any, and
        frees it otherwise."""
        with self._lock:
            _drop_gone(self._queue)
            if not self._queue:
                self._in_flight -= 1
                return
            items = _take(self._queue, self._max_batch)
        # Sent from a thread of its own, so that no caller's thread does work
        # for others. Counted as a call: close waits for it.
        self._client._calls.add()
        threading.Thread(target=self._flush, args=(items,), name="pycent-autobatch", daemon=True).start()

    def _flush(self, items: list[_Queued]) -> None:
        try:
            if not items:
                return
            body = _batch_body(items)
            timeout = _batch_deadline(items, self._client._cfg.request_timeout) - time.monotonic()
            try:
                replies = self._client._send_auto_batch(body, len(items), timeout)
            except Exception as e:
                for q in items:
                    q.error = e
                    q.done.set()
                return
            for q, r in zip(items, replies, strict=True):
                q.reply = r
                q.done.set()
        finally:
            self._release()
            self._client._calls.leave()


class AsyncBatcher:
    """AutoBatch for AsyncClient, on its event loop."""

    def __init__(self, client: Any, opts: AutoBatch) -> None:
        self._client = client
        self._max_in_flight = opts.max_in_flight
        self._max_batch = opts.max_batch_size
        self._in_flight = 0
        self._queue: deque[_Queued] = deque()
        self._tasks: set[asyncio.Task[None]] = set()

    async def call(
        self, method: str, request: Any, deadline: float, alone: Callable[[], Awaitable[_T]]
    ) -> tuple[bool, Any]:
        """As SyncBatcher.call."""
        _drop_gone(self._queue)
        if self._in_flight < self._max_in_flight and not self._queue:
            self._in_flight += 1
            try:
                return True, await alone()
            finally:
                self._release()
        # One thread: nothing frees a slot while the command is encoded.
        q = _Queued(_encode(method, request), deadline, asyncio.get_running_loop().create_future())
        self._queue.append(q)
        fut: asyncio.Future[None] = q.done
        try:
            await asyncio.wait({fut}, timeout=max(0.0, deadline - time.monotonic()))
        except asyncio.CancelledError:
            if not q.taken:
                q.gone = True
            raise
        if not fut.done():
            taken = q.taken
            if not taken:
                q.gone = True
            if taken:
                raise CentTimeoutError(f"{method}: timed out")
            raise CentTimeoutError(f"{method}: timed out before it was sent")
        if q.error is not None:
            raise q.error
        return False, q.reply

    def _release(self) -> None:
        _drop_gone(self._queue)
        if not self._queue:
            self._in_flight -= 1
            return
        items = _take(self._queue, self._max_batch)
        self._client._calls.add()
        task = asyncio.get_running_loop().create_task(self._flush(items))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _flush(self, items: list[_Queued]) -> None:
        try:
            if not items:
                return
            body = _batch_body(items)
            timeout = _batch_deadline(items, self._client._cfg.request_timeout) - time.monotonic()
            try:
                replies = await self._client._send_auto_batch(body, len(items), timeout)
            except Exception as e:
                for q in items:
                    q.error = e
                    if not q.done.done():
                        q.done.set_result(None)
                return
            for q, r in zip(items, replies, strict=True):
                q.reply = r
                if not q.done.done():
                    q.done.set_result(None)
        finally:
            self._release()
            self._client._calls.leave()
