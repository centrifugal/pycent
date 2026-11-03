"""The <method>_all iterators: the items of every page of a paged method
(spec 3.8), written once over the cursor and once for history, for Client
and AsyncClient alike.

Each takes the client's _invoke, sends the request as given, then the next
page, and yields each page's items in order. A page is read when the
iteration reaches it; leaving the loop early reads no further page; an error
ends the iteration, raised where the page would have been.
"""

from __future__ import annotations

import dataclasses
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from cent._api import (
    HistoryRequest,
    HistoryResult,
    MapEntry,
    MapReadStateRequest,
    MapReadStateResult,
    Publication,
    StreamPosition,
)
from cent._errors import InvalidRequestError

Invoke = Callable[[Any, type[Any], float | None], Any]
AsyncInvoke = Callable[[Any, type[Any], float | None], Awaitable[Any]]
# The request of the page after a reply, or None when there is none.
NextPage = Callable[[Any, Any], Any]
# The items a page yields, from its request and reply.
Items = Callable[[Any, Any], list[Any]]


@dataclass(slots=True, kw_only=True)
class HistoryItem(Publication):
    """A publication history_all yields: the Publication, its fields read as
    they are - item.data, item.offset - and the epoch of the stream it is
    in, which position() gives with its offset."""

    epoch: str = ""
    """The epoch of the channel's stream when the page was read."""

    def position(self) -> StreamPosition:
        """The publication's place in the stream: the since of a history call,
        or a client's recover_since, reading what came after it."""
        return StreamPosition(offset=self.offset, epoch=self.epoch)


@dataclass(slots=True, kw_only=True)
class MapStateItem(MapEntry):
    """An entry map_read_state_all yields: the MapEntry, its fields read as
    they are - item.key, item.data - and state, the position the map's state
    was read at."""

    state: StreamPosition = field(default_factory=StreamPosition)
    """The revision the state was read at: the first page's, or the call's
    revision_offset and revision_epoch - what map_read_stream follows the
    state from, as since_offset and since_epoch."""


def _fields(value: Any) -> dict[str, Any]:
    return {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}


def _history_items(req: HistoryRequest, res: HistoryResult) -> list[Any]:
    return [HistoryItem(**_fields(p), epoch=res.epoch) for p in res.publications]


def _map_items(req: MapReadStateRequest, res: MapReadStateResult) -> list[Any]:
    if req.revision_offset or req.revision_epoch:
        state = StreamPosition(offset=req.revision_offset, epoch=req.revision_epoch)
    else:
        state = res.position()
    return [MapStateItem(**_fields(e), state=state) for e in res.entries]


def _attr(name: str) -> Items:
    return lambda _req, res: list(getattr(res, name))


def _check_history(req: HistoryRequest) -> None:
    """history_all's refusals, before anything is sent: a limit below 1 - 0
    asks for the position alone, -1 for everything in one call - and reverse,
    since since has no counterpart running back."""
    if req.limit < 1:
        raise InvalidRequestError("invalid history request: history_all needs a limit of 1 or more: the page size")
    if req.reverse:
        raise InvalidRequestError("invalid history request: history_all reads forward only: reverse is not supported")


def _next_history(req: HistoryRequest, res: HistoryResult) -> HistoryRequest | None:
    """since = the last publication's offset and the result's epoch, until a
    page shorter than the limit."""
    if len(res.publications) < req.limit:
        return None
    return dataclasses.replace(req, since=StreamPosition(offset=res.publications[-1].offset, epoch=res.epoch))


def _by_cursor(cursor: str) -> NextPage:
    """cursor = the reply's field named cursor, until it is empty. The map
    state's later pages are read at the first one's revision, unless the
    request sets one: a reset of the map between pages then fails with
    UnrecoverablePositionError instead of mixing two states."""

    def next_page(req: Any, res: Any) -> Any:
        value: str = getattr(res, cursor)
        if not value:
            return None
        if isinstance(req, MapReadStateRequest) and not req.revision_offset and not req.revision_epoch:
            req = dataclasses.replace(req, revision_offset=res.offset, revision_epoch=res.epoch)
        return dataclasses.replace(req, cursor=value)

    return next_page


def _pages(
    invoke: Invoke, req: Any, result: type[Any], *, items: Items, next_page: NextPage, timeout: float | None
) -> Iterator[Any]:
    while req is not None:
        res = invoke(req, result, timeout)
        yield from items(req, res)
        req = next_page(req, res)


class _AsyncPages:
    """An async iterator over the pages: a class, not an async generator, so
    that leaving the loop early leaves nothing to finalize."""

    __slots__ = ("_buf", "_invoke", "_items", "_next", "_req", "_result", "_timeout")

    def __init__(
        self,
        invoke: AsyncInvoke,
        req: Any,
        result: type[Any],
        *,
        items: Items,
        next_page: NextPage,
        timeout: float | None,
    ) -> None:
        self._invoke, self._req, self._result = invoke, req, result
        self._items, self._next, self._timeout = items, next_page, timeout
        self._buf: deque[Any] = deque()

    def __aiter__(self) -> _AsyncPages:
        return self

    async def __anext__(self) -> Any:
        while not self._buf:
            req, self._req = self._req, None  # an error ends the iteration
            if req is None:
                raise StopAsyncIteration
            res = await self._invoke(req, self._result, self._timeout)
            self._buf.extend(self._items(req, res))
            self._req = self._next(req, res)
        return self._buf.popleft()


def history_all(invoke: Invoke, req: HistoryRequest, timeout: float | None) -> Iterator[Any]:
    _check_history(req)
    return _pages(invoke, req, HistoryResult, items=_history_items, next_page=_next_history, timeout=timeout)


def ahistory_all(invoke: AsyncInvoke, req: HistoryRequest, timeout: float | None) -> AsyncIterator[Any]:
    _check_history(req)
    return _AsyncPages(invoke, req, HistoryResult, items=_history_items, next_page=_next_history, timeout=timeout)


def cursor_all(
    invoke: Invoke, req: Any, result: type[Any], *, items: str, cursor: str, timeout: float | None
) -> Iterator[Any]:
    return _pages(invoke, req, result, items=_items(result, items), next_page=_by_cursor(cursor), timeout=timeout)


def acursor_all(
    invoke: AsyncInvoke, req: Any, result: type[Any], *, items: str, cursor: str, timeout: float | None
) -> AsyncIterator[Any]:
    return _AsyncPages(invoke, req, result, items=_items(result, items), next_page=_by_cursor(cursor), timeout=timeout)


def _items(result: type[Any], name: str) -> Items:
    """The items of a page: a map state's entries with the state's position."""
    return _map_items if result is MapReadStateResult else _attr(name)
