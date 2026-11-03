"""The <method>_all iterators and position(), against a fake Centrifugo (spec 3.8, 15)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import cent
from tests.conftest import Api, Fake

pytestmark = pytest.mark.filterwarnings("error")


def collect(api: Api, method: str, stop: int | None = None, out: list[Any] | None = None, **kw: Any) -> list[Any]:
    """The items of client.<method>_all(**kw), blocking or async alike, into
    out: up to stop of them, leaving the loop then."""
    it = getattr(api.client, method + "_all")(**kw)
    out = [] if out is None else out
    if api.kind == "sync":
        for item in it:
            out.append(item)
            if stop is not None and len(out) == stop:
                break
        return out

    async def run() -> None:
        async for item in it:
            out.append(item)
            if stop is not None and len(out) == stop:
                break

    api.run(run())
    return out


def _pages(fake: Fake, method: str, pages: list[list[Any]], items: str, cursor: str, *, extra: Any = None) -> None:
    """Answers method with pages in turn, the cursor of page i being str(i+1)
    while there are more."""

    def handler(_m: str, body: dict[str, Any]) -> Any:
        i = int(body.get("cursor") or 0)
        out = {items: pages[i], cursor: str(i + 1) if i + 1 < len(pages) else ""}
        if extra is not None:
            out.update(extra(i))
        return out

    fake.on(method, handler)


@dataclass(frozen=True)
class Paged:
    """A method paged by a cursor: its items' field, its cursor's, and the
    field of an item told apart in a test."""

    method: str
    items: str
    cursor: str
    key: str

    def item(self, i: int) -> dict[str, Any]:
        return {self.key: f"{self.key}{i}"}

    def keys(self, got: list[Any]) -> list[str]:
        return [getattr(x, self.key) for x in got]

    def args(self) -> dict[str, Any]:
        return {"channel": "m"} if self.method == "map_read_state" else {}


CURSOR_METHODS = [
    Paged("device_list", "items", "next_cursor", "id"),
    Paged("device_topic_list", "items", "next_cursor", "id"),
    Paged("user_topic_list", "items", "next_cursor", "id"),
    Paged("map_read_state", "entries", "cursor", "key"),
]


@pytest.mark.parametrize("m", CURSOR_METHODS, ids=lambda m: m.method)
@pytest.mark.parametrize("sizes", [[0], [1], [2], [2, 2, 1], [2, 2, 0]])
def test_cursor_pages(api: Api, fake: Fake, m: Paged, sizes: list[int]) -> None:
    # No items, one, exactly a page and several pages: every item once and in
    # order, each request after the first carrying the cursor of the reply
    # before.
    n = 0
    pages = []
    for size in sizes:
        pages.append([m.item(n + j) for j in range(size)])
        n += size
    _pages(fake, m.method, pages, m.items, m.cursor)
    got = collect(api, m.method, limit=2, **m.args())
    assert m.keys(got) == [m.item(j)[m.key] for j in range(n)]
    bodies = fake.bodies(m.method)
    assert len(bodies) == len(sizes)
    assert [b.get("cursor", "") for b in bodies] == [""] + [str(i) for i in range(1, len(sizes))]
    assert all(b["limit"] == 2 for b in bodies)


@pytest.mark.parametrize("m", CURSOR_METHODS, ids=lambda m: m.method)
def test_cursor_leaving_early_reads_no_further_page(api: Api, fake: Fake, m: Paged) -> None:
    _pages(fake, m.method, [[m.item(0), m.item(1)], [m.item(2), m.item(3)], [m.item(4)]], m.items, m.cursor)
    got = collect(api, m.method, stop=3, limit=2, **m.args())
    assert m.keys(got) == [m.item(j)[m.key] for j in range(3)]
    assert len(fake.bodies(m.method)) == 2


@pytest.mark.parametrize("m", CURSOR_METHODS, ids=lambda m: m.method)
def test_cursor_error_ends_after_the_items_before(api: Api, fake: Fake, m: Paged) -> None:
    def handler(_m: str, body: dict[str, Any]) -> Any:
        if body.get("cursor"):
            return cent.ApiError(100, "internal server error")
        return {m.items: [m.item(0), m.item(1)], m.cursor: "next"}

    fake.on(m.method, handler)
    got: list[Any] = []
    with pytest.raises(cent.InternalError):
        collect(api, m.method, out=got, limit=2, **m.args())
    assert m.keys(got) == [m.item(0)[m.key], m.item(1)[m.key]]
    # The iteration has ended: nothing more is read.
    assert len(fake.bodies(m.method)) == 2


def test_map_read_state_all_pins_later_pages_to_the_first_ones_revision(api: Api, fake: Fake) -> None:
    _pages(
        fake,
        "map_read_state",
        [[{"key": "a"}], [{"key": "b"}], [{"key": "c"}]],
        "entries",
        "cursor",
        extra=lambda i: {"offset": 10 + i, "epoch": f"e{i}"},
    )
    assert [e.key for e in collect(api, "map_read_state", channel="m", limit=1)] == ["a", "b", "c"]
    first, *later = fake.bodies("map_read_state")
    assert "revision_offset" not in first
    assert "revision_epoch" not in first
    for b in later:
        assert (b["revision_offset"], b["revision_epoch"]) == (10, "e0")


def test_map_read_state_all_keeps_the_callers_revision(api: Api, fake: Fake) -> None:
    _pages(
        fake,
        "map_read_state",
        [[{"key": "a"}], [{"key": "b"}]],
        "entries",
        "cursor",
        extra=lambda i: {"offset": 10 + i, "epoch": f"e{i}"},
    )
    collect(api, "map_read_state", channel="m", limit=1, revision_offset=5, revision_epoch="x")
    for b in fake.bodies("map_read_state"):
        assert (b["revision_offset"], b["revision_epoch"]) == (5, "x")


def test_map_read_state_all_stale_revision_fails(api: Api, fake: Fake) -> None:
    def handler(_m: str, body: dict[str, Any]) -> Any:
        if body.get("revision_epoch"):
            return cent.ApiError(112, "unrecoverable position")
        return {"entries": [{"key": "a"}], "cursor": "1", "offset": 1, "epoch": "e"}

    fake.on("map_read_state", handler)
    with pytest.raises(cent.UnrecoverablePositionError):
        collect(api, "map_read_state", channel="m", limit=1)


def _history(fake: Fake, total: int, epoch: str = "e") -> None:
    """A history of publications at offsets 1 to total."""

    def handler(_m: str, body: dict[str, Any]) -> Any:
        since = body.get("since", {}).get("offset", 0)
        pubs = [{"data": o, "offset": o} for o in range(since + 1, min(since + body["limit"], total) + 1)]
        return {"publications": pubs, "epoch": epoch, "offset": total}

    fake.on("history", handler)


@pytest.mark.parametrize(("total", "requests"), [(0, 1), (1, 1), (3, 2), (7, 3), (9, 4)])
def test_history_pages(api: Api, fake: Fake, total: int, requests: int) -> None:
    # A full last page costs one more request, which comes back empty.
    _history(fake, total)
    got = collect(api, "history", channel="ch", limit=3)
    assert [p.data for p in got] == list(range(1, total + 1))
    bodies = fake.bodies("history")
    assert len(bodies) == requests
    assert "since" not in bodies[0]
    for i, b in enumerate(bodies[1:], 1):
        assert b["since"] == {"offset": 3 * i, "epoch": "e"}


def test_history_items_carry_their_position(api: Api, fake: Fake) -> None:
    _history(fake, 5, epoch="ep")
    got = collect(api, "history", channel="ch", limit=2)
    assert all(isinstance(p, cent.HistoryItem) and isinstance(p, cent.Publication) for p in got)
    assert [p.position() for p in got] == [cent.StreamPosition(offset=o, epoch="ep") for o in range(1, 6)]
    # Resuming from an item reads what came after it.
    rest = collect(api, "history", channel="ch", limit=10, since=got[2].position())
    assert [p.offset for p in rest] == [4, 5]


def test_map_state_items_carry_the_states_position(api: Api, fake: Fake) -> None:
    _pages(
        fake,
        "map_read_state",
        [[{"key": "a"}], [{"key": "b"}]],
        "entries",
        "cursor",
        extra=lambda i: {"offset": 10 + i, "epoch": f"e{i}"},
    )
    got = collect(api, "map_read_state", channel="m", limit=1)
    assert all(isinstance(e, cent.MapStateItem) and isinstance(e, cent.MapEntry) for e in got)
    assert [(e.key, e.state) for e in got] == [
        ("a", cent.StreamPosition(offset=10, epoch="e0")),
        ("b", cent.StreamPosition(offset=10, epoch="e0")),
    ]
    # With the caller's revision, that is the state's position.
    got = collect(api, "map_read_state", channel="m", limit=1, revision_offset=5, revision_epoch="x")
    assert [e.state for e in got] == [cent.StreamPosition(offset=5, epoch="x")] * 2


def test_history_from_since(api: Api, fake: Fake) -> None:
    _history(fake, 5)
    got = collect(api, "history", channel="ch", limit=10, since=cent.StreamPosition(offset=3, epoch="e"))
    assert [p.offset for p in got] == [4, 5]


def test_history_leaving_early_reads_no_further_page(api: Api, fake: Fake) -> None:
    _history(fake, 9)
    assert len(collect(api, "history", stop=4, channel="ch", limit=2)) == 4
    assert len(fake.bodies("history")) == 2


def test_history_error_ends_after_the_items_before(api: Api, fake: Fake) -> None:
    def handler(_m: str, body: dict[str, Any]) -> Any:
        if "since" in body:
            return cent.ApiError(112, "unrecoverable position")
        return {"publications": [{"data": 1, "offset": 1}, {"data": 2, "offset": 2}], "epoch": "e"}

    fake.on("history", handler)
    got: list[Any] = []
    with pytest.raises(cent.UnrecoverablePositionError):
        collect(api, "history", out=got, channel="ch", limit=2)
    assert [p.data for p in got] == [1, 2]


@pytest.mark.parametrize(
    ("kw", "msg"),
    [
        ({"limit": 0}, "limit of 1 or more"),
        ({"limit": -1}, "limit of 1 or more"),
        ({"limit": 10, "reverse": True}, "reverse is not supported"),
        ({"limit": 10, "channel": ""}, "channel is required"),
    ],
)
def test_history_all_refusals_send_nothing(api: Api, fake: Fake, kw: dict[str, Any], msg: str) -> None:
    # Refused at the call, before iterating.
    with pytest.raises(cent.InvalidRequestError, match=msg):
        api.client.history_all(**{"channel": "ch", **kw})
    assert fake.requests == []


def test_positions(api: Api, fake: Fake) -> None:
    pos = cent.StreamPosition(offset=7, epoch="e7")
    assert cent.PublishResult(offset=7, epoch="e7").position() == pos
    assert cent.HistoryResult(offset=7, epoch="e7").position() == pos
    assert cent.MapReadStateResult(offset=7, epoch="e7").position() == pos
    assert cent.MapReadStreamResult(offset=7, epoch="e7").position() == pos
    assert cent.MapPublishResult(offset=7, epoch="e7").position() == pos
    assert cent.MapRemoveResult(offset=7, epoch="e7").position() == pos
    # Every result holding offset and epoch has it.
    holding = {
        n
        for n in cent._api.__all__
        if isinstance(t := getattr(cent, n), type) and {"offset", "epoch"} <= set(getattr(t, "__slots__", ()))
    }
    assert {n for n in holding if hasattr(getattr(cent, n), "position")} == holding - {"StreamPosition"}
    # What a publish returned is what the next history call asks from.
    res = api.publish(channel="ch", data=1)
    _history(fake, 3)
    api.history(channel="ch", limit=10, since=res.position())
    assert fake.bodies("history")[0]["since"] == {"offset": 1, "epoch": "e1"}
